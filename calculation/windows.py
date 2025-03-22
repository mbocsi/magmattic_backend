from dataclasses import dataclass
from scipy.signal.windows import hann, hamming, blackmanharris, blackman
import numpy as np
from collections.abc import Callable
from type_defs import Window


@dataclass
class WindowProperties:
    name: str
    func: Callable
    coherent_gain: float
    enbw: float


windows: dict[Window, WindowProperties] = {
    "rectangular": WindowProperties(
        name="Rectangular", func=lambda x: np.ones((x,)), coherent_gain=1.0, enbw=1.0
    ),
    "hann": WindowProperties(name="Hann", func=hann, coherent_gain=0.5, enbw=1.5),
    "hamming": WindowProperties(
        name="Hamming", func=hamming, coherent_gain=0.54, enbw=1.37
    ),
    "blackman": WindowProperties(
        name="Blackman", func=blackman, coherent_gain=0.42, enbw=1.73
    ),
    "blackmanharris": WindowProperties(
        name="Blackman-harris", func=blackmanharris, coherent_gain=0.42, enbw=1.71
    ),
}
