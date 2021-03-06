"""
Link Budget and other RF Calculations

References:

 [1] Couch, Leon W.. Digital & Analog Communication Systems.
 [2] Lindgren, M. (2015). A 1296 MHz Earth–Moon–Earth Communication System
     (Master's thesis).

"""
import logging
from math import log10, pi, log2
from . import util


SPEED_OF_LIGHT = 299792458  # in m/s
T0 = 290  # standard room temperature in Kelvin


def eirp(tx_power, tx_dish_gain):
    """Compute the effective isotropically radiated power (EIRP)

    EIRP (dB) = Tx Power (dB) + Tx Antenna Gain (dB).

    Args:
        tx_power     : Transmit power feeding the antenna (dBW).
        tx_dish_gain : Transmit antenna gain (dB).

    Returns:
        The EIRP in dBW.

    """

    eirp = tx_power + tx_dish_gain
    return eirp


def path_loss(d, freq, radar=False, rcs=None, bistatic=False, d_rx=None):
    """Calculate the free-space path loss (or transmission loss)

    This function supports radar mode, in which case it computes the
    transmission loss considering the path loss in the forward and reverse
    paths (to and from the radar object) as well as the scattering at the radar
    object based on its radar cross section.

    Args:
        d        : Distance in meters between transmitter and receiver (e.g.,
                   satellite to ground station) or between the transmitter and
                   the radar object.
        freq     : Carrier frequency in Hz.
        radar    : Radar mode.
        bistatic : Bistatic radar.
        rcs      : Radar cross section (RCS).
        d_rx     : Bistatic radar mode only: distance between radar object and
                   receiver that is not collocated with the transmitter.

    Notes:

        - The RCS definition repeated in [2] is the following: "the RCS of a
          radar object is the hypothetical area intercepting that amount of
          power which, when scattered isotropically, produces a power density
          at the receiver equal to that from the actual object."

    Returns:
        Path loss in dB.

    """
    wavelength = SPEED_OF_LIGHT / freq

    # Eq. 8-11 from [1], or Eq. 3.16 from [2]:
    Lfs_one_way_db = 20*log10(4*pi*d/wavelength)

    if (radar):
        if (rcs is None):
            raise ValueError("Radar cross section required in radar mode")

        # Radar object gain in dB, equation 3.23 in [2]:
        G_obj_db = 10*log10(4*pi*rcs/(wavelength**2))

        if (bistatic):
            if (d_rx is None):
                raise ValueError("Rx distance required in bistatic radar mode")

            Lfs_tx_db = Lfs_one_way_db
            Lfs_rx_db = 20*log10(4*pi*d_rx/wavelength)
            # Bistatic radar transmission loss in dB, equation 3.24 in [2]:
            Lfs_db = Lfs_tx_db + Lfs_rx_db - G_obj_db
        else:
            # Monostatic radar transmission loss in dB, equation 3.26 in [2]:
            Lfs_db = 2*Lfs_one_way_db - G_obj_db
    else:
        Lfs_db = Lfs_one_way_db

    logging.info("Path loss:          {:6.2f} dB".format(Lfs_db))
    return Lfs_db


def dish_gain(diameter, freq):
    """Calculate parabolic dish gain

    The gain in linear units is given by:

    Gain = 4 * 𝜋 * Ae ∕ 𝜆**2,

    where Ae is effective aperture given by:

    Ae = 𝜂 * A,

    and A represents the antenna's physical aperture area.

    Args:
        diameter : Diameter in m
        freq     : Frequency of interest in Hz

    Returns:
        Gain in dB

    """
    radius = diameter / 2
    face_area = pi * (radius**2)  # assume circle
    wavelength = SPEED_OF_LIGHT / freq

    # See Table 8-4 in [1], which assumes a 56% aperture efficiency:
    gain = 7*face_area/(wavelength**2)
    return 10*log10(gain)


def coax_loss_nf(length_ft, Tl=T0):
    """Compute the loss and noise figure of a coaxial RG6 transmission line

    Args:
        length_ft : Line length in feet.
        Tl        : temperature of the line in Kelvin.

    Returns:
        Tuple with line loss (dB) and noise figure (dB).

    """
    loss_db_per_ft = 8/100
    loss_db = length_ft * loss_db_per_ft
    loss = util.db_to_abs(loss_db)

    # The noise figure (dB) of a coaxial line is equal to the loss in dB if the
    # physical temperature of the line is equal to T0=290 K. See Equation 8.32a
    # on Example 8-2 in [1]. More generally, any passive two-port element (or
    # attenuator) at room temperature will have this property (noise figure =
    # attenuation in dB), see Equation 4.22 in [2].
    noise_factor = 1 + (Tl/T0)*(loss - 1)
    noise_fig = 10*log10(noise_factor)

    logging.info("Coax loss:          {:6.2f} dB".format(loss_db))
    logging.info("Coax noise figure:  {:6.2f} dB".format(noise_fig))

    return loss_db, noise_fig


def total_noise_figure(nfs, gains):
    """Calculate the overall noise figure of the receiver system

    Args:
        nfs   : List with the noise figures (in dB) corresponding to the
                cascaded linear devices.
        gains : List with the gains (also in dB) of the cascaded linear
                devices, in the same order as given for "nfs".

    Note: The list of gains should not include the gain of the last device in
    the chain, as it is irrelevant for the overall noise figure computation.

    Returns:
        The overall noise figure in dB

    """

    assert(len(nfs) > 0)
    assert(len(gains) > 0)
    assert(len(gains) == len(nfs) - 1)

    if (len(nfs) == 1):
        return nfs[0]

    # Implement Equation 8-34 from [1]:
    F = util.db_to_abs(nfs[0])
    G_prod = 1
    for i, nf in enumerate(nfs[1:]):
        nf_abs = util.db_to_abs(nf)
        G_prod *= util.db_to_abs(gains[i])
        F += (nf_abs - 1) / G_prod

    F_db = 10*log10(F)
    logging.info("Rx noise figure:    {:6.2f} dB".format(F_db))
    return F_db


def noise_fig_to_noise_temp(nf):
    """Convert noise figure to the effective input-noise temperature

    Note the noise figure is always referenced to a noise source at the
    standard noise temperature of T0 = 290 K. In contrast, the noise
    temperature is independent of the temperature of the noise source.

    Args:
        nf : Noise figure in dB.

    Returns:
        Noise temperature in K.

    """
    nf_abs = util.db_to_abs(nf)

    # Using Equation 8-30b in [1]:
    Te = T0 * (nf_abs - 1)

    return Te


def noise_temp_to_noise_fig(Te):
    """Convert an effective input-noise temperature to a noise figure in dB

    Args:
        Te : Noise temperature in K.

    Returns:
        Noise figure in dB.

    """
    # Noise factor
    nf_abs = 1 + Te/T0
    # Return the noise figure
    return 10*log10(nf_abs)


def rx_sys_noise_temp(Tar, Te):
    """Compute the receiver system noise temperature

    The receiver noise temperature is the sum of the effective input-noise
    temperature (Te) of the entire receiver seen as a blackbox and the antenna
    noise temperature (Tar). The Te term represents the noise introduced by the
    cascaded linear components (e.g., the LNB, the coax line, and the radio
    interface) of the receiver. The Tar component, in turn, is the noise
    captured by the antenna due to the received cosmic noise and Earth
    blackbody radiation. The simplified model is as follows:

    Rx Antenna (Tar) -----> Sum ----> Noise-free Gain Stage ---> Detector
                             ^
                             |
                             |
                      Receiver Noise (Te)

    Note that this is peculiar because the antenna is not treated as another
    cascaded device within the receiver. Instead, the antenna adds to the
    cascaded devices. See Figure 8-24 in [1].

    As explained in [2], around equation 4.39, this is just a convenient choice
    in terms of where the effective input-noise temperature is observed. Note
    that an equivalent (or effective) input noise temperature represents the
    thermodynamic temperature of a noisy resistor, connected to the input of a
    noiseless two-port element, which gives the same output noise power as the
    noisy but otherwise equivalent two-port element, with an ideal noiseless
    source at its input [2]. Hence, if we group the entire receiver into a
    single equivalent two-port element, the Te term represents the noise
    generated by the entire receiver, which has power k*Te*B. When combined to
    the noise collected by the antenna, one obtaines the total system noise
    temperature.

    Args:
        Tar : Antenna noise temperature in K.
        Te  : Effective input-noise temperature in K.

    Returns:
        Receiver system noise temperature in K.

    """

    # Equation 8-41 from [1], or 4.39 from [2]:
    Tsyst = Tar + Te
    logging.info("System noise temp:  {:6.2f} K".format(Tsyst))
    return Tsyst


def cnr(eirp_db, path_loss_db, rx_ant_gain_db, T_sys_db, bw):
    """Compute the carrier-to-noise ratio (CNR) in dB

    Args:
        eirp_db        : EIRP in dBW.
        path_loss_db   : Free-space path loss in dB.
        rx_ant_gain_db : Receiver antenna gain in dB.
        T_sys_db       : Receiver system noise temperature in dBK.
        bw             : Nominal signal bandwidth.

    Returns:
        CNR (also known as C/N) in dB.

    """
    # According to Equation 8-40 in [1], the noise power is given by N =
    # k*Tsyst*bw, where k is the Boltzmann constant, Tsyst is the receiver
    # system noise temperature (in absolute units) and bw is the IF equivalent
    # bandwidth in Hz. On the C/N computation in dB, given that N is in the
    # denominator, we can simply subtract k_db, Tsyst_db, and B_db. See
    # Equation 8-43 in [1].
    k_db = -228.6  # Boltzmann’s constant (of 1.38e-23) in dB
    bw_db = 10*log10(bw)

    # The received power level at the antenna terminals is of interest, so
    # print it it out:
    P_rx_dbw = eirp_db - path_loss_db + rx_ant_gain_db
    P_rx_dbm = P_rx_dbw + 30
    logging.info("Rx Power:           {:6.2f} dBm".format(P_rx_dbm))

    # The ratio between the Rx antenna gain and the receiver noise temperature,
    # usually known as G/T, is also a metric of interest. Print it:
    g_over_t_db = rx_ant_gain_db - T_sys_db
    logging.info("(G/T):              {:6.2f} dB/K".format(g_over_t_db))

    # C/N, as computed in Equation 8-43 from [1]:
    cnr_db = eirp_db - path_loss_db + g_over_t_db - k_db - bw_db
    logging.info("(C/N):              {:6.2f} dB".format(cnr_db))

    return cnr_db


def capacity(snr_db, bw):
    """Compute the channel capacity in bps

    Args:
        snr_db : signal-to-noise ratio in dB.
        bw     : nominal bandwidth.

    Returns:
        Capacity in bits per second (bps).

    """
    snr = util.db_to_abs(snr_db)
    c = bw * log2(1 + snr)
    logging.info("Capacity:           {}".format(util.format_rate(c)))
    return c
