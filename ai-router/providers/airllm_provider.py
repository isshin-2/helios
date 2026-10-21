import asyncio
import logging
import os
import sys
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from providers.base import BaseProvider

logger = logging.getLogger("helios.providers.airllm")

# Try importing AirLLM from local reference repo or site-packages
AIRLLM_AVAILABLE = False
try:
    import airllm
    from airllm import AutoModel
    AIRLLM_AVAILABLE = True
except ImportError:
    ref_repo_path = os.path.join(os.path.expanduser("~"), "Documents", "ref repos", "airllm", "air_llm")
    if os.path.exists(ref_repo_path):
        if ref_repo_path not in sys.path:
            sys.path.insert(0, ref_repo_path)
        try:
            from airllm import AutoModel
            AIRLLM_AVAILABLE = True
        except Exception as e:
            logger.warning(f"Could not load AirLLM from ref repos: {e}")
            AIRLLM_AVAILABLE = False

class AirLLMProvider(BaseProvider):
    """
    Ultra-Low VRAM Provider using AirLLM's layered block-wise streaming inference.
    Executes large 32B-70B models on budget local hardware (VRAM < 4GB)
    by streaming layers sequentially from disk to GPU/RAM on-demand.
    """

    def __init__(self, default_model: str = "Qwen/Qwen2.5-Coder-7B", device: str = "cpu", max_seq_len: int = 1024):
        self.default_model = default_model
        self.device = device
        self.max_seq_len = max_seq_len
        self.active_models: Dict[str, Any] = {}
        self.is_available = AIRLLM_AVAILABLE
        logger.info(f"[AirLLM] Initialized AirLLMProvider (available={self.is_available}, device={self.device})")

    def _get_or_load_model(self, model_name: str):
        if not self.is_available:
            raise RuntimeError("AirLLM runtime is not installed or available.")
        if model_name not in self.active_models:
            logger.info(f"[AirLLM] Instantiating layered model on meta-device: {model_name}")
            model = AutoModel.from_pretrained(
                model_name,
                device=self.device,
                max_seq_len=self.max_seq_len,
                prefetching=True
            )
            self.active_models[model_name] = model
        return self.active_models[model_name]

    def _sync_generate(self, model_instance, prompt: str, max_new_tokens: int = 128) -> str:
        input_tokens = model_instance.tokenizer(
            [prompt],
            return_tensors="pt",
            truncation=True,
            max_length=self.max_seq_len,
            padding=False
        )
        tokens = input_tokens['input_ids']
        if self.device != "cpu":
            tokens = tokens.to(self.device)

        generation_output = model_instance.generate(
            tokens,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            return_dict_in_generate=True
        )
        return model_instance.tokenizer.decode(generation_output.sequences[0], skip_special_tokens=True)

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        # Format messages into single prompt
        prompt = ""
        for m in messages:
            role = m.get("role", "user").capitalize()
            content = m.get("content", "")
            prompt += f"{role}: {content}\n"
        prompt += "Assistant: "

        max_tokens = 256
        if options and "num_predict" in options:
            max_tokens = options["num_predict"]

        result_text = await self.generate_text(model, prompt, max_tokens=max_tokens)
        response_data = {
            "model": model,
            "message": {"role": "assistant", "content": result_text},
            "done": True
        }

        if stream:
            async def _stream_gen():
                yield response_data
            return _stream_gen()
        return response_data

    async def generate_text(self, model: str, prompt: str, max_tokens: int = 256) -> str:
        loop = asyncio.get_running_loop()
        try:
            model_inst = self._get_or_load_model(model or self.default_model)
            text = await loop.run_in_executor(None, self._sync_generate, model_inst, prompt, max_tokens)
            return text
        except Exception as e:
            logger.error(f"[AirLLM] Execution failed for model {model}: {e}")
            return f"[AirLLM Error]: {str(e)}"

    async def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        max_tokens = 256
        if options and "num_predict" in options:
            max_tokens = options["num_predict"]
        text = await self.generate_text(model, prompt, max_tokens)
        res = {"model": model, "response": text, "done": True}
        if stream:
            async def _gen():
                yield res
            return _gen()
        return res

    async def get_embeddings(self, model: str, prompt: str) -> List[float]:
        # Fallback dummy embedding vector for interface compliance
        return [0.0] * 384

    async def list_models(self) -> Dict[str, Any]:
        return {
            "models": [
                {"name": name, "details": {"family": "airllm", "parameter_size": "layered-stream"}}
                for name in self.active_models.keys()
            ]
        }

    async def list_running(self) -> Dict[str, Any]:
        return {"models": list(self.active_models.keys())}

    async def unload_model(self, model: str) -> Dict[str, Any]:
        if model in self.active_models:
            del self.active_models[model]
            import gc
            gc.collect()
            return {"status": "unloaded", "model": model}
        return {"status": "not_loaded", "model": model}
