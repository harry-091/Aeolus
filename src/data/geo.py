"""
Antarctic Geographic Foundation Utilities

Reusable geographic constants and functions for Antarctic analysis.
Handles latitude/longitude conventions, Antarctic region definitions,
and coordinate validation for polar stereographic grids.

Dataset Reference:
- NSIDC Sea Ice Polar Stereographic South: EPSG:3412
- Antarctic coverage: lat -90 to -39.36, lon -180 to 180
- Grid resolution: 25 km x 25 km
"""
import numpy as np


# ---------------------------------------------------------------------------
# Antarctic Geographic Constants
# ---------------------------------------------------------------------------

# Antarctic boundary latitude (approximately the northernmost extent of
# the sea-ice zone; NSIDC CDR south grid extends to -39.36 deg)
ANTARCTIC_NORTH_LAT = -39.36  # degrees

# South Pole
SOUTH_POLE_LAT = -90.0

# Longitude range
LON_MIN = -180.0
LON_MAX = 180.0

# NSIDC polar stereographic south grid dimensions (25 km)
# Full grid: 316 columns x 332 rows
NSIDC_SOUTH_GRID_COLS = 316
NSIDC_SOUTH_GRID_ROWS = 332

# Valid SIC range (fraction 0-1)
SIC_MIN = 0.0
SIC_MAX = 1.0

# Land/missing value masks
SIC_LAND_VALUE = 254.0   # in byte-scaled data (254 = land)
SIC_MISSING_VALUE = 255.0  # in byte-scaled data (255 = missing)
SIC_FILL_VALUE = -9999.0


# ---------------------------------------------------------------------------
# Coordinate Validation
# ---------------------------------------------------------------------------

def validate_latitude(lat):
    """Check if a latitude value is in valid Antarctic range."""
    if isinstance(lat, (list, np.ndarray)):
        lat = np.asarray(lat)
        return np.all((lat >= SOUTH_POLE_LAT) & (lat <= 0.0))
    return SOUTH_POLE_LAT <= lat <= 0.0


def validate_longitude(lon):
    """Check if a longitude value is in valid range [-180, 180]."""
    if isinstance(lon, (list, np.ndarray)):
        lon = np.asarray(lon)
        return np.all((lon >= LON_MIN) & (lon <= LON_MAX))
    return LON_MIN <= lon <= LON_MAX


def is_antarctic_region(lat, lon=None):
    """
    Check if coordinates fall within the Antarctic region.

    Parameters
    ----------
    lat : float or array-like
        Latitude in degrees (-90 to 0).
    lon : float or array-like, optional
        Longitude in degrees (-180 to 180).

    Returns
    -------
    bool or np.ndarray of bool
        True if coordinate is in the Antarctic region.
    """
    lat = np.asarray(lat)
    result = lat <= ANTARCTIC_NORTH_LAT
    if lon is not None:
        lon = np.asarray(lon)
        result = result & (lon >= LON_MIN) & (lon <= LON_MAX)
    return bool(result) if result.ndim == 0 else result


# ---------------------------------------------------------------------------
# Grid Helpers
# ---------------------------------------------------------------------------

def antarctic_bbox():
    """
    Return bounding box for the Antarctic region.

    Returns
    -------
    dict with keys: south, north, west, east (in degrees)
    """
    return {
        "south": SOUTH_POLE_LAT,
        "north": ANTARCTIC_NORTH_LAT,
        "west": LON_MIN,
        "east": LON_MAX,
    }


def make_latlon_grid(nrows=332, ncols=316, lat_min=-89.84, lat_max=-39.36,
                     lon_min=-180.0, lon_max=180.0):
    """
    Create a simple latitude/longitude grid covering the Antarctic region.

    Note: This is an approximation. The actual NSIDC polar stereographic
    grid has non-uniform lat/lon spacing. For real gridded data, the
    coordinates are provided in the NetCDF file.

    Parameters
    ----------
    nrows : int
        Number of latitude rows.
    ncols : int
        Number of longitude columns.
    lat_min, lat_max : float
        Latitude bounds (degrees).
    lon_min, lon_max : float
        Longitude bounds (degrees).

    Returns
    -------
    lat_grid, lon_grid : np.ndarray
        2D arrays of shape (nrows, ncols).
    """
    lats = np.linspace(lat_max, lat_min, nrows)
    lons = np.linspace(lon_min, lon_max, ncols)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return lat_grid, lon_grid


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Compute great-circle distance between two points using Haversine formula.

    Parameters
    ----------
    lat1, lon1 : float
        Coordinates of point 1 in degrees.
    lat2, lon2 : float
        Coordinates of point 2 in degrees.

    Returns
    -------
    float
        Distance in kilometers.
    """
    R = 6371.0  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


# ---------------------------------------------------------------------------
# Antarctic Base Map
# ---------------------------------------------------------------------------

def create_antarctic_base_map(figsize=(10, 10), title="Antarctic Region"):
    """
    Create a reusable Antarctic base geographic map using matplotlib.

    Uses a South Pole stereographic projection without Cartopy.
    Provides latitude/longitude gridlines and Antarctic continent outline.

    Parameters
    ----------
    figsize : tuple
        Figure size (width, height).
    title : str
        Plot title.

    Returns
    -------
    fig, ax : matplotlib Figure and Axes
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": "polar"})

    # South Pole is at the center, so theta=0 is along the prime meridian
    # and angles go clockwise (eastward) when viewed from above the South Pole
    ax.set_theta_zero_location("N")  # 0 degrees at top (Greenwich)
    ax.set_theta_direction(-1)       # Clockwise (eastward)

    # Set radial limits (latitude)
    ax.set_ylim(0, 90)  # 0 = South Pole, 90 = equator (in polar coords)
    ax.set_yticks([0, 15, 30, 50, 70, 90])
    ax.set_yticklabels(["90S", "75S", "60S", "40S", "20S", "0"])
    ax.set_rlabel_position(135)

    # Set angular ticks (longitude)
    ax.set_xticks([0, np.pi/4, np.pi/2, 3*np.pi/4, np.pi,
                   5*np.pi/4, 3*np.pi/2, 7*np.pi/4])
    ax.set_xticklabels(["0", "45E", "90E", "135E", "180",
                        "135W", "90W", "45W"])

    # Draw Antarctic continent outline (simplified polygon)
    # Approximate coastline at ~70S latitude with some detail
    continent_lons = np.array([
        -60, -55, -50, -45, -40, -35, -30, -25, -20, -15, -10, -5, 0,
        5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75,
        80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140,
        145, 150, 155, 160, 165, 170, 175, 180,
        -175, -170, -165, -160, -155, -150, -145, -140, -135, -130,
        -125, -120, -115, -110, -105, -100, -95, -90, -85, -80, -75, -70, -65, -60
    ])
    # Approximate Antarctic latitude at each longitude
    continent_lats = np.array([
        62, 63, 64, 66, 67, 68, 69, 70, 70, 71, 71, 70, 70,
        69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 60, 61, 62, 63, 64,
        65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77,
        78, 77, 76, 75, 74, 73, 72, 71,
        70, 69, 68, 67, 66, 65, 64, 63, 62, 61,
        60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 62
    ])

    # Convert to radians (colatitude = 90 - latitude)
    theta = np.radians(continent_lons)
    r = 90 - continent_lats  # colatitude

    # Fill continent
    ax.fill(theta, r, color="lightgray", alpha=0.6, zorder=2)
    ax.plot(theta, r, color="black", linewidth=0.8, zorder=3)

    # Add the South Pole point
    ax.plot(0, 0, "k*", markersize=10, zorder=5)
    ax.annotate("South Pole", xy=(0, 0), xytext=(0.3, 5),
                fontsize=8, ha="center", zorder=5)

    # Grid and styling
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    return fig, ax


# ---------------------------------------------------------------------------
# Forecast Map
# ---------------------------------------------------------------------------

def create_forecast_map(forecast_ds, risk_ds=None, figsize=(12, 10)):
    """
    Create Antarctic forecast map showing current SIC, forecast SIC, and risk.

    Parameters
    ----------
    forecast_ds : xarray.Dataset
        Must contain 'sic_current' and 'sic_forecast' with lat/lon coords.
    risk_ds : xarray.Dataset, optional
        Must contain 'risk' variable with lat/lon coords.
    figsize : tuple
        Figure size.

    Returns
    -------
    fig, axes : matplotlib Figure and array of Axes
    """
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm

    n_plots = 3 if risk_ds is not None else 2
    fig, axes = plt.subplots(1, n_plots, figsize=figsize,
                             subplot_kw={"projection": "polar"})

    if n_plots == 2:
        axes = [axes[0], axes[1], None]

    sic_cmap = plt.cm.Blues_r
    risk_colors = ["#2ecc71", "#f39c12", "#e74c3c", "#8e44ad"]
    risk_cmap = ListedColormap(risk_colors)
    risk_norm = BoundaryNorm([0, 1, 2, 3, 4], risk_cmap.N)

    lats = forecast_ds.lat.values
    lons = forecast_ds.lon.values
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    theta = np.radians(lon_grid)
    r = 90 - lat_grid  # colatitude

    plots = [
        ("Current SIC", forecast_ds["sic_current"].values, sic_cmap, 0, 1),
        ("Forecast SIC", forecast_ds["sic_forecast"].values, sic_cmap, 0, 1),
    ]
    if risk_ds is not None:
        plots.append(("Navigation Risk", risk_ds["risk"].values, risk_cmap, 0, 3))

    for idx, (title, data, cmap, vmin, vmax) in enumerate(plots):
        if axes[idx] is None:
            continue
        ax = axes[idx]
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 90)
        ax.set_yticks([0, 15, 30, 50, 70])
        ax.set_yticklabels(["90S", "75S", "60S", "40S", "20S"])
        ax.set_xticks([0, np.pi/2, np.pi, 3*np.pi/2])
        ax.set_xticklabels(["0", "90E", "180", "90W"])

        # Draw continent
        clons = np.linspace(-180, 180, 73)
        clats_cont = np.interp(clons,
            [-60,-30,0,30,60,90,120,150,180],
            [62,69,70,65,77,71,60,62,62])
        ctheta = np.radians(clons)
        cr = 90 - clats_cont
        ax.fill(ctheta, cr, color="lightgray", alpha=0.5, zorder=2)
        ax.plot(ctheta, cr, color="black", linewidth=0.5, zorder=3)

        # Plot data
        im = ax.pcolormesh(theta, r, data, cmap=cmap, vmin=vmin, vmax=vmax,
                           zorder=4, shading="auto")

        ax.set_title(title, fontsize=12, fontweight="bold", pad=15)
        plt.colorbar(im, ax=ax, shrink=0.6, pad=0.1)

    # Add risk legend
    if risk_ds is not None and axes[2] is not None:
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#2ecc71", label="LOW (<0.15)"),
            Patch(facecolor="#f39c12", label="MODERATE (0.15-0.50)"),
            Patch(facecolor="#e74c3c", label="HIGH (0.50-0.80)"),
            Patch(facecolor="#8e44ad", label="VERY HIGH (>=0.80)"),
        ]
        axes[2].legend(handles=legend_elements, loc="lower center",
                       fontsize=8, bbox_to_anchor=(0.5, -0.1))

    # Add date info
    if "current_date" in forecast_ds.attrs:
        fig.suptitle(
            f"Antarctic SIC Forecast: {forecast_ds.attrs['current_date']} -> "
            f"{forecast_ds.attrs.get('forecast_date', 'N/A')}",
            fontsize=14, fontweight="bold", y=1.02
        )

    plt.tight_layout()
    return fig, axes


# ---------------------------------------------------------------------------
# Iceberg Trajectory Map
# ---------------------------------------------------------------------------

def create_iceberg_map(track_df, prediction_df=None, figsize=(10, 10)):
    """
    Create Antarctic map showing iceberg track and predicted trajectory.

    Parameters
    ----------
    track_df : pd.DataFrame
        Historical track with latitude, longitude columns.
    prediction_df : pd.DataFrame, optional
        Predicted trajectory with latitude, longitude, step columns.
    figsize : tuple
        Figure size.

    Returns
    -------
    fig, ax : matplotlib Figure and Axes
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 90)
    ax.set_yticks([0, 15, 30, 50, 70])
    ax.set_yticklabels(["90S", "75S", "60S", "40S", "20S"])
    ax.set_xticks([0, np.pi/2, np.pi, 3*np.pi/2])
    ax.set_xticklabels(["0", "90E", "180", "90W"])

    # Draw continent
    clons = np.linspace(-180, 180, 73)
    clats_cont = np.interp(clons,
        [-60,-30,0,30,60,90,120,150,180],
        [62,69,70,65,77,71,60,62,62])
    ctheta = np.radians(clons)
    cr = 90 - clats_cont
    ax.fill(ctheta, cr, color="lightgray", alpha=0.5, zorder=2)
    ax.plot(ctheta, cr, color="black", linewidth=0.5, zorder=3)

    # Historical track
    lats = track_df["latitude"].values
    lons = track_df["longitude"].values
    theta = np.radians(lons)
    r = 90 - lats

    ax.plot(theta, r, "b-", linewidth=1.5, alpha=0.7, label="Historical track", zorder=5)
    ax.scatter(theta[:1], r[:1], c="green", s=100, zorder=6, label="Start")
    ax.scatter(theta[-1:], r[-1:], c="blue", s=100, zorder=6, label="Latest")

    # Predicted trajectory
    if prediction_df is not None:
        pred_lats = prediction_df["latitude"].values
        pred_lons = prediction_df["longitude"].values
        pred_theta = np.radians(pred_lons)
        pred_r = 90 - pred_lats
        ax.plot(pred_theta, pred_r, "r--", linewidth=2, alpha=0.8,
                label="Predicted trajectory", zorder=5)
        ax.scatter(pred_theta[-1:], pred_r[-1:], c="red", s=120, marker="*",
                   zorder=6, label="Predicted position")

    ax.legend(loc="lower left", fontsize=9)
    ax.set_title("Iceberg Trajectory", fontsize=14, fontweight="bold", pad=15)

    plt.tight_layout()
    return fig, ax
