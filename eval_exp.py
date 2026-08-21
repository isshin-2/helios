import asyncio
from skills.self_modification.workspace import ExperimentWorkspace, transition_experiment, Actor, ExperimentStatus
from security.permissions import PermissionManager
from skills.self_modification.benchmark import BenchmarkRunner

async def run_eval():
    pm = PermissionManager()
    ws = ExperimentWorkspace(pm)
    br = BenchmarkRunner(helios_dir="C:\\Users\\krithik\\Documents\\ai-router")
    
    experiment_id = "change_20260820_015_132521"
    transition_experiment(experiment_id, ExperimentStatus.EVALUATING, Actor.SYSTEM, "Running evaluation")
    
    success, metrics = await br.run_benchmarks(experiment_id)
    print("Benchmark Success:", success)
    print("Metrics:", metrics)
    
    if success:
        transition_experiment(experiment_id, ExperimentStatus.READY_FOR_REVIEW, Actor.SYSTEM, "Evaluation passed")
        print("Experiment is READY_FOR_REVIEW")
    else:
        transition_experiment(experiment_id, ExperimentStatus.FAILED, Actor.SYSTEM, "Evaluation failed")
        print("Experiment FAILED")

if __name__ == "__main__":
    asyncio.run(run_eval())
