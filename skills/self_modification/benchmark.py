"""
HELIOS — Benchmarking Framework
================================
Provides empirical evaluation of experiments using isolated subprocesses.

SECURITY MODEL (Subprocess Isolation):
    The benchmark subprocess runs with a MINIMAL allowlisted environment.
    This prevents leaking API keys, tokens, credentials, or secrets.
    
    However, a normal Python subprocess is NOT a security sandbox.
    The experiment code can still:
      - Access arbitrary filesystem locations (read)
      - Spawn child processes
      - Import production modules via fallback
      - Consume unbounded memory/CPU (only constrained by timeout)
      - Access the network
    
    PYTHONPATH is used for module selection, NOT as a security boundary.
    Full OS-level isolation (e.g., Windows Job Objects, containers) is
    a future hardening phase.
"""

import json
import logging
import math
import statistics
import subprocess
import os
import time
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import BenchmarkResult, BenchmarkComparison, EvaluationSummary
from core.platform.process import launch_isolated_process, kill_process_tree

logger = logging.getLogger(__name__)

MIN_SUCCESSFUL_SAMPLES = 3

_ALLOWED_ENV_KEYS = frozenset({
    "PATH", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "TEMP", "TMP",
    "WINDIR", "PATHEXT", "HOME", "USER", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "VIRTUAL_ENV",
})


@dataclass
class MetricDefinition:
    name: str
    direction: Literal["higher_is_better", "lower_is_better"]
    critical: bool = False


@dataclass
class BenchmarkDefinition:
    id: str
    name: str
    metrics: List[MetricDefinition]
    iterations: int
    warmup_iterations: int
    timeout_seconds: float


# Example registry
BENCHMARK_REGISTRY: Dict[str, BenchmarkDefinition] = {
    "routing_latency": BenchmarkDefinition(
        id="routing_latency",
        name="Tool Routing Latency",
        metrics=[
            MetricDefinition(name="process_latency_ms", direction="lower_is_better", critical=True)
        ],
        iterations=5,
        warmup_iterations=1,
        timeout_seconds=30.0
    )
}

class BenchmarkRunner:
    def __init__(self, helios_dir: str):
        self.helios_dir = helios_dir
        self.benchmarks_dir = os.path.join(helios_dir, "benchmarks")

    def _build_safe_env(self, is_baseline: bool, experiment_dir: Optional[str]) -> Dict[str, str]:
        env: Dict[str, str] = {}
        for key in _ALLOWED_ENV_KEYS:
            val = os.environ.get(key)
            if val is not None:
                env[key] = val
        if not is_baseline and experiment_dir:
            modified_dir = os.path.join(experiment_dir, "modified")
            env["PYTHONPATH"] = modified_dir + os.pathsep + env.get("PYTHONPATH", "")
        return env

    def _validate_metrics(self, metrics: Dict[str, Any], expected_metrics: List[MetricDefinition]) -> Optional[Dict[str, float]]:
        # Obsolete since we don't have self_reported metrics anymore, but kept for compatibility
        pass

    def _kill_process_tree(self, proc: subprocess.Popen):
        """Terminate a process and its children to prevent runaway benchmarks."""
        kill_process_tree(proc)

    def _run_single(self, benchmark_id: str, timeout: float, is_baseline: bool, 
                    experiment_dir: Optional[str],
                    expected_metrics: Optional[List[MetricDefinition]] = None) -> Optional[Dict[str, float]]:
        script_path = os.path.join(self.benchmarks_dir, f"{benchmark_id}.py")
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Benchmark script not found: {script_path}")
            
        env = self._build_safe_env(is_baseline, experiment_dir)
        sandbox_path = os.path.join(self.helios_dir, "skills", "self_modification", "sandbox.py")
        
        try:
            start_time = time.perf_counter()
            proc = launch_isolated_process(
                ["python", sandbox_path, script_path],
                env=env,
                cwd=self.helios_dir
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            end_time = time.perf_counter()
            process_latency_ms = (end_time - start_time) * 1000.0
            
            if proc.returncode != 0:
                logger.warning(f"Benchmark {benchmark_id} failed (exit {proc.returncode}): {stderr[:500]}")
                return None
                
            final_metrics = {}
            if expected_metrics:
                for m in expected_metrics:
                    if m.name == "process_latency_ms":
                        final_metrics["process_latency_ms"] = process_latency_ms

            return final_metrics
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Benchmark {benchmark_id} timed out after {timeout}s")
            self._kill_process_tree(proc)
            return None
        except Exception as e:
            logger.warning(f"Benchmark {benchmark_id} execution error: {e}")
            return None

    def run_benchmark(self, definition: BenchmarkDefinition, is_baseline: bool, 
                      experiment_dir: Optional[str] = None) -> Dict[str, BenchmarkResult]:
        metrics_data: Dict[str, List[float]] = {m.name: [] for m in definition.metrics}
        
        total_runs = definition.warmup_iterations + definition.iterations
        for i in range(total_runs):
            res = self._run_single(
                definition.id, definition.timeout_seconds, 
                is_baseline, experiment_dir,
                expected_metrics=definition.metrics
            )
            if res:
                if i >= definition.warmup_iterations:
                    for m in definition.metrics:
                        if m.name in res:
                            metrics_data[m.name].append(res[m.name])
                            
        results = {}
        for m in definition.metrics:
            data = metrics_data[m.name]
            if len(data) < MIN_SUCCESSFUL_SAMPLES:
                logger.warning(
                    f"Metric '{m.name}' has only {len(data)} samples "
                    f"(minimum {MIN_SUCCESSFUL_SAMPLES}). Marking INCONCLUSIVE."
                )
                results[m.name] = BenchmarkResult(sample_count=len(data))
                continue
                
            results[m.name] = BenchmarkResult(
                mean=statistics.mean(data),
                median=statistics.median(data),
                min_val=min(data),
                max_val=max(data),
                p95=self._percentile(data, 0.95),
                std_dev=statistics.stdev(data) if len(data) > 1 else 0.0,
                sample_count=len(data)
            )
            
        return results

    @staticmethod
    def _percentile(data: List[float], p: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        n = len(sorted_data)
        if n == 1:
            return sorted_data[0]
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)

    def evaluate_metric(self, metric_def: MetricDefinition, baseline: BenchmarkResult, experiment: BenchmarkResult) -> BenchmarkComparison:
        if baseline.mean is None or experiment.mean is None:
            return BenchmarkComparison(
                metric=metric_def.name,
                direction=metric_def.direction,
                baseline=baseline,
                experiment=experiment,
                change_percent=None,
                result="INCONCLUSIVE"
            )
        
        if not math.isfinite(baseline.mean) or not math.isfinite(experiment.mean):
            return BenchmarkComparison(
                metric=metric_def.name,
                direction=metric_def.direction,
                baseline=baseline,
                experiment=experiment,
                change_percent=None,
                result="INCONCLUSIVE"
            )
        
        if baseline.sample_count < MIN_SUCCESSFUL_SAMPLES or experiment.sample_count < MIN_SUCCESSFUL_SAMPLES:
            return BenchmarkComparison(
                metric=metric_def.name,
                direction=metric_def.direction,
                baseline=baseline,
                experiment=experiment,
                change_percent=None,
                result="INCONCLUSIVE"
            )
            
        if baseline.mean == 0:
            if experiment.mean == 0:
                change_percent = 0.0
            else:
                change_percent = 100.0 if experiment.mean > 0 else -100.0
        else:
            change_percent = ((experiment.mean - baseline.mean) / baseline.mean) * 100
        
        if not math.isfinite(change_percent):
            return BenchmarkComparison(
                metric=metric_def.name,
                direction=metric_def.direction,
                baseline=baseline,
                experiment=experiment,
                change_percent=None,
                result="INCONCLUSIVE"
            )
        
        cv = experiment.std_dev / experiment.mean if experiment.mean != 0 else 0
        if not math.isfinite(cv):
            cv = 0
            
        if cv > 0.20: 
            result = "UNSTABLE"
        else:
            if metric_def.direction == "lower_is_better":
                is_improvement = change_percent < -2.0
                is_regression = change_percent > 2.0
            else:
                is_improvement = change_percent > 2.0
                is_regression = change_percent < -2.0
                
            if is_improvement:
                result = "IMPROVEMENT"
            elif is_regression:
                if metric_def.critical and abs(change_percent) > 5.0:
                    result = "CRITICAL_REGRESSION"
                else:
                    result = "REGRESSION"
            else:
                result = "NEUTRAL"
                
        return BenchmarkComparison(
            metric=metric_def.name,
            direction=metric_def.direction,
            baseline=baseline,
            experiment=experiment,
            change_percent=change_percent,
            result=result
        )

def build_evaluation_summary(comparisons: List[BenchmarkComparison], baseline_hash: str) -> EvaluationSummary:
    crit_regressions = [c.metric for c in comparisons if c.result == "CRITICAL_REGRESSION"]
    regressions = [c.metric for c in comparisons if c.result == "REGRESSION"]
    improvements = [c.metric for c in comparisons if c.result == "IMPROVEMENT"]
    unstable = [c.metric for c in comparisons if c.result == "UNSTABLE"]
    inconclusive = [c.metric for c in comparisons if c.result == "INCONCLUSIVE"]
    
    if crit_regressions:
        classification = "CRITICAL_REGRESSION"
    elif regressions:
        classification = "REGRESSION"
    elif inconclusive or unstable:
        classification = "INCONCLUSIVE" if inconclusive else "UNSTABLE"
    elif improvements:
        classification = "IMPROVEMENT"
    else:
        classification = "NEUTRAL"
        
    summary = EvaluationSummary(
        classification=classification,
        timestamp=datetime.now(timezone.utc).isoformat(),
        baseline_hash=baseline_hash
    )
    summary.critical_regressions = crit_regressions
    for c in comparisons:
        summary.comparisons[c.metric] = c
    return summary
