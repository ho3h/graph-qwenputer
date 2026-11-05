import gc, sys
for k in list(globals()):
    if k not in ("TL", "ctx", "t_import") and not k.startswith("__"):
        del globals()[k]
import gc, torch, sys
sys.last_traceback = None; sys.last_value = None; sys.last_exc = None
gc.collect(); torch.mps.empty_cache()
print(torch.mps.current_allocated_memory() / 2**30, torch.mps.driver_allocated_memory() / 2**30)
