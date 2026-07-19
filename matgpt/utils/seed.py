from __future__ import annotations

import os
import random

import numpy as np
import torch


def set_seed(seed: int, deterministic: bool = False) -> None:

    # Give Python's random-number system the starting seed.
    random.seed(seed)

    # Give NumPy's random-number system the same seed.
    np.random.seed(seed)

    # Give PyTorch's CPU random-number system the same seed.
    torch.manual_seed(seed)

    # If a GPU is available, seed its random-number systems too.
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    os.environ["PYTHONHASHSEED"] = str(seed)
    if deterministic:
        # Ask PyTorch to prefer repeatable calculation methods.
        torch.use_deterministic_algorithms(True, warn_only=True)

        # Disable automatic searching for the fastest GPU method.
        torch.backends.cudnn.benchmark = False
    else:
        # Allow PyTorch to search for faster GPU methods.
        torch.backends.cudnn.benchmark = True
