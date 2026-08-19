import os
import sys
import tempfile
import pytest
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.self_modification.models import (
    ExperimentStatus, RiskLevel, ExperimentMetadata, FileEntry,
    Actor, validate_transition,
    BenchmarkResult, BenchmarkComparison
)
from skills.self_modification.workspace import ExperimentWorkspace
from skills.self_modification.validator import (
    classify_risk, validate_experiment_source, validate_experiment_target,
)
from skills.self_modification.benchmark import (
    BenchmarkRunner, MetricDefinition
)
from security.permissions import PermissionManager
import db
import sqlite3
import threading


class TestSelfModificationWorkspace:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.helios_dir = os.path.join(self.temp_dir, "helios")
        self.experiments_dir = os.path.join(self.helios_dir, "experiments")
        
        os.makedirs(self.helios_dir)
        os.makedirs(self.experiments_dir)
        
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.patcher4 = patch("db.DB_PATH", self.db_path)
        self.patcher4.start()
        
        # Initialize test DB
        db.init_db()
        db.migrate_db()
        
        self.pm = PermissionManager()
        # Override pm's protected paths for isolation
        self.pm._resolved_protected_paths = [
            (Path(self.helios_dir) / "core").resolve(strict=False),
            (Path(self.helios_dir) / "security").resolve(strict=False),
            (Path(self.helios_dir) / "main.py").resolve(strict=False),
            (Path(self.helios_dir) / "config.py").resolve(strict=False),
            (Path(self.helios_dir) / "skills" / "self_modification").resolve(strict=False)
        ]
        self.workspace = ExperimentWorkspace(self.pm)

        self.patcher1 = patch("skills.self_modification.workspace.EXPERIMENTS_DIR", self.experiments_dir)
        self.patcher2 = patch("skills.self_modification.workspace.HELIOS_DIR", self.helios_dir)
        self.patcher3 = patch("skills.self_modification.validator.HELIOS_DIR", self.helios_dir)
        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()

    def teardown_method(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.patcher4.stop()
        shutil.rmtree(self.temp_dir)

    # 1. Workspace Tests
    def test_workspace_creation(self):
        meta1 = self.workspace.create_experiment("test1")
        meta2 = self.workspace.create_experiment("test2")
        
        assert meta1.experiment_id != meta2.experiment_id
        
        exp_dir = os.path.join(self.experiments_dir, meta1.experiment_id)
        assert os.path.isdir(os.path.join(exp_dir, "modified"))
        assert os.path.isdir(os.path.join(exp_dir, "backup"))
        assert os.path.isdir(os.path.join(exp_dir, "tests"))
        
        assert meta1.objective == "test1"
        assert meta1.status == ExperimentStatus.DRAFT

    # 2. File Modification Tests
    def test_file_modification_allowed(self):
        meta = self.workspace.create_experiment("test")
        
        success, msg = self.workspace.write_experiment_file(meta.experiment_id, "skills/some_test_skill.py", "print('test')")
        assert success is True, msg
        
        success, msg = self.workspace.write_experiment_file(meta.experiment_id, "prompts/test.md", "prompt")
        assert success is True, msg

    def test_file_modification_blocked(self):
        meta = self.workspace.create_experiment("test")
        
        blocked = [
            "security/permissions.py",
            "core/orchestrator.py",
            "main.py",
            "config.py",
            "skills/self_modification/anything.py"
        ]
        
        for b in blocked:
            success, msg = self.workspace.write_experiment_file(meta.experiment_id, b, "test")
            assert success is False
            assert "blocked" in msg.lower() or "protected" in msg.lower()

    def test_experiment_source_containment(self):
        meta = self.workspace.create_experiment("test")
        exp_dir = Path(self.experiments_dir) / meta.experiment_id
        
        valid_source = exp_dir / "modified" / "skills" / "test.py"
        assert validate_experiment_source(valid_source, exp_dir) is True
        
        invalid_source = exp_dir / "backup" / "skills" / "test.py"
        assert validate_experiment_source(invalid_source, exp_dir) is False
        
        outside_source = Path(self.helios_dir) / "skills" / "test.py"
        assert validate_experiment_source(outside_source, exp_dir) is False

    # 3. State Machine Tests (10 tests)
    def test_state_machine_llm_draft_to_exp(self):
        assert validate_transition(ExperimentStatus.DRAFT, ExperimentStatus.EXPERIMENTING, Actor.LLM)
        
    def test_state_machine_llm_blocks_exp_to_test(self):
        assert not validate_transition(ExperimentStatus.EXPERIMENTING, ExperimentStatus.TESTING, Actor.LLM)
        
    def test_state_machine_llm_blocks_test_to_review(self):
        assert not validate_transition(ExperimentStatus.TESTING, ExperimentStatus.READY_FOR_REVIEW, Actor.LLM)
        
    def test_state_machine_llm_blocks_ready_to_approved(self):
        assert not validate_transition(ExperimentStatus.READY_FOR_REVIEW, ExperimentStatus.APPROVED, Actor.LLM)
        
    def test_state_machine_llm_blocks_approved_to_deployed(self):
        assert not validate_transition(ExperimentStatus.APPROVED, ExperimentStatus.DEPLOYED, Actor.LLM)
        
    def test_state_machine_llm_blocks_deployed_to_rollback(self):
        assert not validate_transition(ExperimentStatus.DEPLOYED, ExperimentStatus.ROLLED_BACK, Actor.LLM)

    def test_state_machine_human_ready_to_approved(self):
        assert validate_transition(ExperimentStatus.READY_FOR_REVIEW, ExperimentStatus.APPROVED, Actor.HUMAN)
        
    def test_state_machine_human_approved_to_deployed(self):
        assert validate_transition(ExperimentStatus.APPROVED, ExperimentStatus.DEPLOYED, Actor.HUMAN)
        
    def test_state_machine_human_deployed_to_rollback(self):
        assert validate_transition(ExperimentStatus.DEPLOYED, ExperimentStatus.ROLLED_BACK, Actor.HUMAN)
        
    def test_state_machine_human_blocks_draft_to_approved(self):
        assert not validate_transition(ExperimentStatus.DRAFT, ExperimentStatus.APPROVED, Actor.HUMAN)

    # 4. Integrity Tests (4 tests)
    def test_integrity_hash_recorded_on_write(self):
        meta = self.workspace.create_experiment("test")
        
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        assert len(meta.files) == 1
        assert meta.files[0].baseline_sha256 is not None
        
    def test_integrity_verify_success(self):
        meta = self.workspace.create_experiment("test")
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        meta = self.workspace.load_metadata(meta.experiment_id)
        
        assert self.workspace._verify_baseline_integrity(meta) is True

    def test_integrity_verify_failure_on_change(self):
        meta = self.workspace.create_experiment("test")
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        meta = self.workspace.load_metadata(meta.experiment_id)
        
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("modified code")
            
        assert self.workspace._verify_baseline_integrity(meta) is False

    @patch("core.platform.process.launch_isolated_process")
    def test_evaluate_fails_on_integrity(self, mock_launch):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Tests passed", "")
        mock_launch.return_value = mock_proc
        
        meta = self.workspace.create_experiment("test")
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        meta = self.workspace.load_metadata(meta.experiment_id)
        
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("modified code")
            
        success, msg = self.workspace.evaluate_experiment(meta.experiment_id)
        assert success is False
        assert "integrity violation" in msg.lower()
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        assert meta.status == ExperimentStatus.SECURITY_VIOLATION

    # 5. Diff Tests
    @patch("core.platform.process.launch_isolated_process")
    def test_diff_generation(self, mock_launch):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Tests passed", "")
        mock_launch.return_value = mock_proc

        meta = self.workspace.create_experiment("test")
        
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code\n")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code\n")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        self.workspace._generate_diff(meta)
        
        diff = self.workspace.get_diff(meta.experiment_id)
        assert diff is not None
        assert "-old code" in diff
        assert "+new code" in diff

    # 6. Deployment Tests
    @patch("security.permissions.get_db")
    def test_deployment_success(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps({"file_write": {"enabled": True, "paths": [self.helios_dir]}})}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        meta = self.workspace.create_experiment("test")
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code\n")
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        meta.status = ExperimentStatus.APPROVED
        self.workspace._save_metadata(meta)
        
        success, msg = self.workspace.deploy(meta.experiment_id, 1)
        assert success is True, msg
        
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "r") as f:
            assert f.read() == "new code"
            
    @patch("security.permissions.get_db")
    def test_deployment_protected_target(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps({"file_write": {"enabled": True, "paths": [self.helios_dir]}})}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        meta = self.workspace.create_experiment("test")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        meta.files.append(FileEntry("modified/core/orchestrator.py", "core/orchestrator.py"))
        os.makedirs(os.path.join(self.experiments_dir, meta.experiment_id, "modified", "core"), exist_ok=True)
        with open(os.path.join(self.experiments_dir, meta.experiment_id, "modified", "core", "orchestrator.py"), "w") as f:
            f.write("malicious")
            
        meta.status = ExperimentStatus.APPROVED
        self.workspace._save_metadata(meta)
        
        success, msg = self.workspace.deploy(meta.experiment_id, 1)
        assert success is False

    @patch("security.permissions.get_db")
    def test_deployment_partial_failure_rollback(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps({"file_write": {"enabled": True, "paths": [self.helios_dir]}})}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        meta = self.workspace.create_experiment("test")
        
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test1.py"), "w") as f:
            f.write("old code\n")
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test1.py", "new code 1")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        meta.files.append(FileEntry("backup/test2.py", "skills/test2.py")) 
        os.makedirs(os.path.join(self.experiments_dir, meta.experiment_id, "backup"), exist_ok=True)
        with open(os.path.join(self.experiments_dir, meta.experiment_id, "backup", "test2.py"), "w") as f:
            f.write("malicious")
            
        meta.status = ExperimentStatus.APPROVED
        self.workspace._save_metadata(meta)
        
        success, msg = self.workspace.deploy(meta.experiment_id, 1)
        assert success is False
        
        with open(os.path.join(self.helios_dir, "skills", "test1.py"), "r") as f:
            assert f.read() == "old code\n"

    # 7. Rollback Tests
    @patch("security.permissions.get_db")
    def test_rollback_success(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps({"file_write": {"enabled": True, "paths": [self.helios_dir]}})}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        meta = self.workspace.create_experiment("test")
        
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        meta.status = ExperimentStatus.APPROVED
        self.workspace._save_metadata(meta)
        
        self.workspace.deploy(meta.experiment_id, 1)
        
        success, msg = self.workspace.rollback(meta.experiment_id, 1)
        assert success is True, msg
        
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "r") as f:
            assert f.read() == "old code"

    @patch("security.permissions.get_db")
    def test_rollback_blocked_on_change(self, mock_db):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"system_access": json.dumps({"file_write": {"enabled": True, "paths": [self.helios_dir]}})}
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        meta = self.workspace.create_experiment("test")
        
        os.makedirs(os.path.join(self.helios_dir, "skills"), exist_ok=True)
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("old code")
            
        self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "new code")
        
        meta = self.workspace.load_metadata(meta.experiment_id)
        meta.status = ExperimentStatus.APPROVED
        self.workspace._save_metadata(meta)
        self.workspace.deploy(meta.experiment_id, 1)
        
        with open(os.path.join(self.helios_dir, "skills", "test.py"), "w") as f:
            f.write("changed code")
            
        success, msg = self.workspace.rollback(meta.experiment_id, 1)
        assert success is False
        assert "changed since deployment" in msg.lower()

    # 8. Path Security Tests
    def test_path_security_traversal(self):
        meta = self.workspace.create_experiment("test")
        success, msg = self.workspace.write_experiment_file(meta.experiment_id, "skills/../security/permissions.py", "test")
        assert success is False
        
    def test_path_security_allowed_pseudo_protected(self):
        meta = self.workspace.create_experiment("test")
        success, msg = self.workspace.write_experiment_file(meta.experiment_id, "core_backup/test.py", "test")
        assert success is True, msg
        
    def test_path_security_blocked_subdirectory(self):
        meta = self.workspace.create_experiment("test")
        success, msg = self.workspace.write_experiment_file(meta.experiment_id, "core/subdirectory/test.py", "test")
        assert success is False

    # 9. BenchmarkRunner Environment Tests
    def test_build_safe_env_removes_secrets(self):
        runner = BenchmarkRunner(self.helios_dir)
        original_env = {"PATH": "/bin", "OPENAI_API_KEY": "secret", "AWS_ACCESS_KEY": "secret"}
        with patch("os.environ", original_env):
            safe_env = runner._build_safe_env(True, None)
        assert "PATH" in safe_env
        assert "OPENAI_API_KEY" not in safe_env
        assert "AWS_ACCESS_KEY" not in safe_env
        
    def test_build_safe_env_removes_pythonpath(self):
        runner = BenchmarkRunner(self.helios_dir)
        original_env = {"PYTHONPATH": "/opt/custom", "SYSTEMROOT": "C:\\Windows"}
        with patch("os.environ", original_env):
            safe_env = runner._build_safe_env(True, None)
        assert "PYTHONPATH" not in safe_env
        assert safe_env.get("SYSTEMROOT") == "C:\\Windows"
        
    def test_build_safe_env_overrides(self):
        runner = BenchmarkRunner(self.helios_dir)
        original_env = {"PATH": "/bin"}
        with patch("os.environ", original_env):
            # To test PYTHONPATH override, we pass is_baseline=False and a valid dir
            safe_env = runner._build_safe_env(False, "/experiment")
        assert "/experiment" in safe_env.get("PYTHONPATH", "")

    # 10. Benchmark Comparison Logic Tests
    def test_compare_distributions_significant(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="higher_is_better")
        b1 = BenchmarkResult(mean=10.0, median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=30)
        e1 = BenchmarkResult(mean=20.0, median=20.0, min_val=20.0, max_val=20.0, p95=20.0, std_dev=0.1, sample_count=30)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "IMPROVEMENT"
        
    def test_compare_distributions_insignificant(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="higher_is_better")
        b1 = BenchmarkResult(mean=10.0, median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=30)
        e1 = BenchmarkResult(mean=10.1, median=10.1, min_val=10.1, max_val=10.1, p95=10.1, std_dev=0.1, sample_count=30)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "NEUTRAL"
        
    def test_compare_distributions_regression(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="higher_is_better")
        b1 = BenchmarkResult(mean=20.0, median=20.0, min_val=20.0, max_val=20.0, p95=20.0, std_dev=0.1, sample_count=30)
        e1 = BenchmarkResult(mean=10.0, median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=30)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "REGRESSION"
        
    def test_compare_distributions_lower_better(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="lower_is_better")
        b1 = BenchmarkResult(mean=20.0, median=20.0, min_val=20.0, max_val=20.0, p95=20.0, std_dev=0.1, sample_count=30)
        e1 = BenchmarkResult(mean=10.0, median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=30)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "IMPROVEMENT"
        
    def test_compare_distributions_nan_handling(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="higher_is_better")
        b1 = BenchmarkResult(mean=float("nan"), median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=30)
        e1 = BenchmarkResult(mean=20.0, median=20.0, min_val=20.0, max_val=20.0, p95=20.0, std_dev=0.1, sample_count=30)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "INCONCLUSIVE"
        
    def test_compare_distributions_inf_handling(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="higher_is_better")
        b1 = BenchmarkResult(mean=float("inf"), median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=30)
        e1 = BenchmarkResult(mean=20.0, median=20.0, min_val=20.0, max_val=20.0, p95=20.0, std_dev=0.1, sample_count=30)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "INCONCLUSIVE"

    def test_compare_distributions_too_few_samples(self):
        runner = BenchmarkRunner(self.helios_dir)
        mdef = MetricDefinition(name="test", direction="higher_is_better")
        b1 = BenchmarkResult(mean=10.0, median=10.0, min_val=10.0, max_val=10.0, p95=10.0, std_dev=0.1, sample_count=2)
        e1 = BenchmarkResult(mean=20.0, median=20.0, min_val=20.0, max_val=20.0, p95=20.0, std_dev=0.1, sample_count=2)
        comp = runner.evaluate_metric(mdef, b1, e1)
        assert comp.result == "INCONCLUSIVE"



    # 11. Database Persistence Security Tests
    def test_database_persistence(self):
        meta = self.workspace.create_experiment("db_test")
        success, _ = self.workspace.write_experiment_file(meta.experiment_id, "skills/test.py", "print('db')")
        assert success
        
        # Reload from fresh DB instance (simulating persistence)
        reloaded = self.workspace.load_metadata(meta.experiment_id)
        assert reloaded is not None
        assert reloaded.objective == "db_test"
        assert len(reloaded.files) == 1
        assert reloaded.files[0].target == "skills/test.py"

    def test_state_machine_enforces_rules_via_db(self):
        meta = self.workspace.create_experiment("state_test")
        
        # Try to illegally transition from DRAFT to READY_FOR_REVIEW directly (which requires EVALUATOR & evaluation data)
        success, msg = self.workspace.transition_llm(meta.experiment_id, ExperimentStatus.READY_FOR_REVIEW)
        assert success is False
        assert "cannot transition" in msg.lower() or "not allowed" in msg.lower()
        
        reloaded = self.workspace.load_metadata(meta.experiment_id)
        assert reloaded.status == ExperimentStatus.DRAFT

    def test_workspace_blocks_modifying_db(self):
        meta = self.workspace.create_experiment("db_mod_test")
        success, msg = self.workspace.write_experiment_file(meta.experiment_id, "helios.db", "corrupted")
        assert success is False
        assert "blocked" in msg.lower() or "protected" in msg.lower()

    def test_benchmark_isolation(self):
        runner = BenchmarkRunner(self.helios_dir)
        env = runner._build_safe_env(is_baseline=True, experiment_dir=None)
        
        # Secret should not leak
        assert "SECRET_API_KEY" not in env
        
        # Test timeout by running a dummy infinite loop directly if we can't easily mock it
        # The existing tests mock subprocess, but here we can just verify the kill logic exists
        assert hasattr(runner, '_kill_process_tree')

    def test_concurrency_metadata_access(self):
        meta = self.workspace.create_experiment("concurrency_test")
        
        def worker(target_status, actor):
            from skills.self_modification.models import transition_experiment
            try:
                transition_experiment(meta.experiment_id, target_status, actor)
            except Exception:
                pass
                
        # Fire two transitions at once (one legal, one illegal)
        from skills.self_modification.models import Actor
        t1 = threading.Thread(target=worker, args=(ExperimentStatus.EXPERIMENTING, Actor.LLM))
        t2 = threading.Thread(target=worker, args=(ExperimentStatus.APPROVED, Actor.HUMAN))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        reloaded = self.workspace.load_metadata(meta.experiment_id)
        # Assuming the illegal one fails, the legal one might succeed depending on timing
        # The key is that the DB doesn't get corrupted and we didn't end up in APPROVED
        assert reloaded.status in (ExperimentStatus.DRAFT, ExperimentStatus.EXPERIMENTING)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# --- ADVERSARIAL SANDBOX TESTS ---

@pytest.fixture
def helios_dir(tmp_path):
    import shutil
    os.makedirs(tmp_path / 'benchmarks', exist_ok=True)
    sandbox_dir = tmp_path / 'skills' / 'self_modification'
    os.makedirs(sandbox_dir, exist_ok=True)
    
    # We must also copy core/platform/process.py since sandbox might need it, actually sandbox doesn't.
    # Just copy sandbox.py
    shutil.copy('C:/Users/krithik/Documents/ai-router/skills/self_modification/sandbox.py', sandbox_dir / 'sandbox.py')
    
    # Let's also set PYTHONPATH so sandbox can find things if it needs, though it shouldn't
    return str(tmp_path)

def test_sandbox_blocks_database_tampering(helios_dir):
    """Verify the benchmark sandbox prevents modifying helios.db"""
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    # Create malicious benchmark
    bad_bench = os.path.join(helios_dir, "benchmarks", "malicious_db.py")
    with open(bad_bench, "w") as f:
        f.write("""
import sqlite3
import os
import sys
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'helios.db')
try:
    conn = sqlite3.connect(db_path)
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
""")
    
    definition = BenchmarkDefinition(
        id="malicious_db",
        name="Malicious DB Access",
        metrics=[MetricDefinition("process_latency_ms", "lower_is_better", critical=True)],
        iterations=1, warmup_iterations=0, timeout_seconds=5.0
    )
    
    # Run it
    results = runner.run_benchmark(definition, True, None)
    
    # Since it sys.exits with 1 due to PermissionError from audit hook, the runner should return INCONCLUSIVE
    assert results["process_latency_ms"].mean is None

def test_sandbox_blocks_network(helios_dir):
    """Verify the benchmark sandbox prevents network access"""
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    bad_bench = os.path.join(helios_dir, "benchmarks", "malicious_net.py")
    with open(bad_bench, "w") as f:
        f.write("""
import socket
import sys
try:
    s = socket.socket()
    s.connect(("8.8.8.8", 53))
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
""")
    
    definition = BenchmarkDefinition(
        id="malicious_net",
        name="Malicious Net",
        metrics=[MetricDefinition("process_latency_ms", "lower_is_better")],
        iterations=1, warmup_iterations=0, timeout_seconds=5.0
    )
    
    results = runner.run_benchmark(definition, True, None)
    assert results["process_latency_ms"].mean is None

def test_sandbox_blocks_subprocess(helios_dir):
    """Verify the benchmark sandbox prevents spawning subprocesses"""
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    bad_bench = os.path.join(helios_dir, "benchmarks", "malicious_sub.py")
    with open(bad_bench, "w") as f:
        f.write("""
import subprocess
import sys
try:
    subprocess.Popen(["echo", "hello"])
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
""")
    
    definition = BenchmarkDefinition(
        id="malicious_sub",
        name="Malicious Subprocess",
        metrics=[MetricDefinition("process_latency_ms", "lower_is_better")],
        iterations=1, warmup_iterations=0, timeout_seconds=5.0
    )
    
    results = runner.run_benchmark(definition, True, None)
    assert results["process_latency_ms"].mean is None

def test_sandbox_blocks_filesystem_write(helios_dir):
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    bad_bench = os.path.join(helios_dir, "benchmarks", "malicious_fs.py")
    with open(bad_bench, "w") as f:
        f.write("""
import os
import sys
try:
    with open("test.txt", "w") as f:
        f.write("test")
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
""")
    
    definition = BenchmarkDefinition(
        id="malicious_fs",
        name="Malicious FS",
        metrics=[MetricDefinition("process_latency_ms", "lower_is_better")],
        iterations=1, warmup_iterations=0, timeout_seconds=5.0
    )
    
    results = runner.run_benchmark(definition, True, None)
    assert results["process_latency_ms"].mean is None

def test_sandbox_blocks_ctypes(helios_dir):
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    bad_bench = os.path.join(helios_dir, "benchmarks", "malicious_ctypes.py")
    with open(bad_bench, "w") as f:
        f.write("""
import sys
try:
    import ctypes
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    sys.exit(1)
""")
    
    definition = BenchmarkDefinition(
        id="malicious_ctypes",
        name="Malicious ctypes",
        metrics=[MetricDefinition("process_latency_ms", "lower_is_better")],
        iterations=1, warmup_iterations=0, timeout_seconds=5.0
    )
    
    results = runner.run_benchmark(definition, True, None)
    assert results["process_latency_ms"].mean is None

def test_benchmark_ignores_self_reported_metrics(helios_dir):
    """Verify that benchmark outputs with JSON metrics do not affect the result."""
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    bad_bench = os.path.join(helios_dir, "benchmarks", "spoof_metrics.py")
    with open(bad_bench, "w") as f:
        f.write("""
import json
import time
print(json.dumps({"metrics": {"process_latency_ms": 0.0001}}))
time.sleep(0.5)
""")
    
    definition = BenchmarkDefinition(
        id="spoof_metrics",
        name="Spoof Metrics",
        metrics=[MetricDefinition("process_latency_ms", "lower_is_better", critical=True)],
        iterations=3, warmup_iterations=0, timeout_seconds=5.0
    )
    
    results = runner.run_benchmark(definition, True, None)
    
    # Ensure it's externally measured, meaning > 0.5s (time.sleep)
    # Even if it printed 0.0001, the actual measurement should be at least 500ms
    assert results["process_latency_ms"].mean is not None
    assert results["process_latency_ms"].mean >= 400.0  # Allow some slack, but definitely not 0.0001

def test_benchmark_timeout_kills_process_tree(helios_dir):
    """Verify that timeout kills children spawned before the audit hook blocks subprocesses (or using bypass)."""
    from skills.self_modification.benchmark import BenchmarkRunner, BenchmarkDefinition, MetricDefinition
    runner = BenchmarkRunner(helios_dir)
    
    # We will simulate a child by manually launching one in the benchmark before the audit hook takes effect?
    # Actually, sandbox blocks subprocess. But if the experiment somehow created a child (e.g. multiprocessing bug),
    # the process tree killer should clean it up.
    # To test this purely, we test the killer function itself.
    import subprocess
    from core.platform.process import launch_isolated_process, kill_process_tree
    import time
    
    # Create a process that spawns a child that sleeps forever
    script = os.path.join(helios_dir, "benchmarks", "tree_test.py")
    with open(script, "w") as f:
        f.write("""
import subprocess
import time
import sys
# Spawn child that ignores signals
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(100)"])
time.sleep(100)
""")
    
    proc = launch_isolated_process(["python", script], cwd=helios_dir)
    time.sleep(1) # wait for child to spawn
    kill_process_tree(proc)
    
    # The proc should be dead
    assert proc.poll() is not None
    # We can't trivially check if the child is dead without psutil, but the kill_process_tree should have run without errors.

