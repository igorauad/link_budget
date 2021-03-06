"""
Satellite look angle computations

References:

 [1] https://www.ngs.noaa.gov/CORS/Articles/SolerEisemannJSE.pdf.
 [2] https://en.wikipedia.org/wiki/Earth_radius.

"""
import logging
from math import sqrt, sin, asin, cos, acos, tan, atan, atan2, degrees, \
    radians
import numpy as np


def _look_angles_ellipsoidal(sat_long, rx_long, rx_lat, rx_height=0,
                             sat_alt=35786e3):
    """Calculate look angles (elevation, azimuth) and slant range

    Computation using the rigorous ellipsoidal approach presented in [1].

    Args:
        sat_long   : Subsatellite point's geodetic longitude
        rx_long    : Longitude of the receiver station in degrees
        rx_lat     : Geodetic latitute of the receiver station in degrees
        rx_height  : Orthometric height (height above sea-evel)
        sat_alt    : Satellite/reflector altitude in meters (default to
                     the geosynchronous altitude)

    Returns:
        Tuple with elevation (degrees), azimuth (degrees) and slant range (m).

    """

    # Step 1: PROGRAM INPUTS

    # Convert to radians
    sat_long = radians(sat_long)
    rx_long = radians(rx_long)
    rx_lat = radians(rx_lat)

    # Step 2: TRANSFORMATION CURVILINEAR TO CARTESIAN COORDINATES

    # Ellipsoid parameters from GRS80
    f_inv = 298.257222100882711  # reciprocal flattening
    f = 1 / f_inv  # flattening
    e_sq = 2*f - f**2  # eccentricity squared

    # Earth parameters
    R_eq = 6378.137e3   # equatorial radius in meters (see [4])
    r = R_eq + sat_alt  # from the earth's center to the spacecraft

    # Principal radius of curvature in the prime vertical (see the the
    # discussion below Eq 12 in [1]). The computation is also discussed in [4].
    N = R_eq / sqrt(1 - e_sq * sin(rx_lat)**2)

    # Ellipsoidal (geodetic) height of the antenna location:
    Ng = 0  # undulation of the geoid or geoid height
    h = Ng + rx_height

    # Rectangular coordinates of the antenna location, using Eq. 12 from [1]:
    x_p = (N + h) * cos(rx_long) * cos(rx_lat)
    y_p = (N + h) * sin(rx_long) * cos(rx_lat)
    z_p = (N*(1 - e_sq) + h) * sin(rx_lat)

    # Rectangular coordinates of the satellite. See Fig. 5 in [1]:
    x_s = r * cos(sat_long)
    y_s = r * sin(sat_long)
    z_s = 0

    # Step 3: SATELLITE COMPONENTS ON LOCAL (x, y, z) COORDINATES
    rect_coor = np.array([x_s, y_s, z_s]) - np.array([x_p, y_p, z_p])

    # rect_coor is a vector starting on the receiver position P and ending on
    # the satellite S (i.e., the topocentric range PS). In other words, it
    # represents the satellite rectangular coordinates referenced to the
    # receiver position. The Euclidean norm of the vector is the slant (or
    # topocentric) range:
    slant_range = np.linalg.norm(rect_coor)

    # Step 4: SATELLITE COMPONENTS ON LOCAL (e, n, u)
    #
    # e-axis points to (geodetic) east; n to (geodetic) north; and u to
    # (geodetic) zenith.

    # Rotation matrix - Eq. 9b from [1]:
    rot_mtx = np.array([
        [-sin(rx_long), cos(rx_long), 0],
        [-sin(rx_lat)*cos(rx_long), -sin(rx_lat)*sin(rx_long), cos(rx_lat)],
        [cos(rx_lat)*cos(rx_long), cos(rx_lat)*sin(rx_long), sin(rx_lat)]
    ])
    # Conversion using Eq. 10 [1]:
    geodetic_coor = np.dot(rot_mtx, rect_coor)

    # Step 5: GEODETIC AZIMUTH AND GEODETIC VERTICAL ANGLE
    e, n, u = geodetic_coor
    azimuth = atan2(e, n)
    vert_angle = atan(u / sqrt(e**2 + n**2))  # elevation

    azimuth_degrees = degrees(azimuth) % 360
    elevation_degrees = degrees(vert_angle)
    return elevation_degrees, azimuth_degrees, slant_range


def _look_angles_spherical(sat_long, rx_long, rx_lat, sat_alt=35786e3):
    """Calculate look angles (elevation, azimuth) and slant range

    Computation using the spherical approximation discussed in [1].

    Args:
        sat_long   : Subsatellite point's geodetic longitude
        rx_long    : Longitude of the receiver station in degrees
        rx_lat     : Geodetic latitute of the receiver station in degrees
        sat_alt    : Satellite/reflector altitude in meters (default to
                     the geosynchronous altitude)

    Returns:
        Tuple with elevation (degrees), azimuth (degrees) and slant range (m).

    """
    # Convert to radians
    sat_long = radians(sat_long)
    rx_long = radians(rx_long)
    rx_lat = radians(rx_lat)

    # Constants
    R = 6371e3          # mean radius of the earth in meters
    R_eq = 6378.137e3   # equatorial radius in meters (see [4])
    r = R_eq + sat_alt  # from the earth's center to the spacecraft

    # Eq. (1) from [1]:
    cos_gamma = cos(rx_lat) * cos(sat_long - rx_long)
    gamma = acos(cos_gamma)
    # gamma is the angle between the radius vectors to the Rx location and the
    # sub-satellite point (intersection with the earth's surface of the
    # geocentric radius vector to the satellite). Equation (1) is the cosine of
    # the this angle.

    # Distance between the satellite and the receiver (a.k.a. slant range),
    # from Equation (2) of [1]:
    d = r * sqrt(1 + (R/r)**2 - 2*(R/r)*cos_gamma)

    # Zenith distance, Equation (4) from [1]:
    z = asin((r/d)*sin(gamma))

    # Elevation:
    v = 90 - degrees(z)

    # Angle of Equation (6) from [1]:
    beta = degrees(acos(tan(rx_lat)/tan(gamma)))

    # Azimuth:
    if (rx_lat > 0):
        # Rx is north of the satellite
        if (sat_long < rx_long):
            # Satellite to SW
            alpha = 180 + beta
        else:
            # Satellite to SE
            alpha = 180 - beta
    else:
        # Rx is south of the satellite
        if (sat_long < rx_long):
            # Satellite to NW
            alpha = 360 - beta
        else:
            # Satellite to NE
            alpha = beta

    return v, alpha, d


def look_angles(sat_long, rx_long, rx_lat, sat_alt=35786e3,
                implementation='ellipsoidal'):
    """Calculate look angles (elevation, azimuth) and slant range

    Computes the angles relative to a reflector, either active (satellite) or
    passive (radar object). Assumes the reflector is located above the equator
    (latitude 0) and that the Rx station is at sea level.

    Args:
        sat_long   : Subsatellite point's geodetic longitude
        rx_long    : Longitude of the receiver station in degrees
        rx_lat     : Geodetic latitute of the receiver station in degrees
        sat_alt    : Satellite/reflector altitude in meters (default to
                     the geosynchronous altitude)

    Note:
        - Positive longitudes are east, whereas negative longitudes are to the
          west.

    Returns:
        Tuple with elevation (degrees), azimuth (degrees) and slant range (m).

    """
    if (implementation == 'ellipsoidal'):
        elev, azt, d = _look_angles_ellipsoidal(sat_long, rx_long, rx_lat,
                                                sat_alt=sat_alt)
    else:
        elev, azt, d = _look_angles_spherical(sat_long, rx_long, rx_lat,
                                              sat_alt=sat_alt)

    logging.info("Elevation:          {:6.2f} degrees".format(elev))
    logging.info("Azimuth:            {:6.2f} degrees".format(azt))
    logging.info("Distance:           {:8.2f} km".format(d/1e3))

    return elev, azt, d
