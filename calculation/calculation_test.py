import matplotlib.pyplot as plt
import numpy as np


def calc_fft(data, T, Ntot, Nsig) -> tuple[np.ndarray, np.ndarray]:
    # Perform fft
    fft = np.fft.rfft(data, n=Ntot) / Nsig
    print(fft)
    magnitude = np.abs(fft)
    magnitude[1:-1] = 2 * magnitude[1:-1]

    phase = np.angle(fft)

    freq = np.fft.rfftfreq(Ntot, d=T / Nsig)

    freq = freq.reshape((len(freq), 1))
    magnitude = magnitude.reshape((len(magnitude), 1))
    phase = phase.reshape((len(phase), 1))

    mag_data = np.hstack((freq, magnitude))
    phase_data = np.hstack((freq, phase))

    return mag_data, phase_data


signal = np.cos(np.linspace(0, 10 * np.pi, 1000) + 0.5)

mag, phase = calc_fft(signal, 1, 1000, 1000)

threshold = 0.1

# Mask the phase where the magnitude is below the threshold
# masked_phase = np.where(mag >= threshold, phase, 0)
# phase[mag >= threshold]
masked_phase = phase
masked_phase[mag[:, 1] < threshold, 1] = 0

# print(phase[:, 1])
plt.plot(mag[:, 0], mag[:, 1])
plt.plot(phase[:, 0], phase[:, 1])
plt.show()
