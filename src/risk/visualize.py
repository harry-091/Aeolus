"""Risk map visualization for Phase 4.

Generates Antarctic navigation risk maps with color-coded risk classes.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import xarray as xr


RISK_COLORS = {
    0: "#2ecc71",  # LOW - green
    1: "#f39c12",  # MODERATE - orange
    2: "#e67e22",  # HIGH - dark orange
    3: "#e74c3c",  # VERY HIGH - red
}

RISK_LABELS = {
    0: "LOW",
    1: "MODERATE",
    2: "HIGH",
    3: "VERY HIGH",
}


def plot_risk_map(risk_dataset, save_path="data/processed/navigation_risk_map.png", title="Antarctic Navigation Risk"):
    """Plot the combined navigation risk map.

    Args:
        risk_dataset: xr.Dataset from build_risk_dataset.
        save_path: where to save the PNG.
        title: map title.

    Returns:
        str: path to saved file.
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 10), subplot_kw={"projection": "polar"})

    lats = risk_dataset.lat.values
    lons = risk_dataset.lon.values
    risk_class = risk_dataset["risk_class"].values

    # Build polar coordinate grids
    theta = np.radians(lons)
    r = 90 - lats  # colatitude

    # Create proper meshgrid for pcolormesh
    # Need (n_lon+1) x (n_lat+1) edges for pcolormesh with n_lat x n_lon cells
    theta_edges = np.linspace(theta[0] - np.radians(3), theta[-1] + np.radians(3), len(lons) + 1)
    r_edges = np.linspace(r[0] - (r[1] - r[0]) / 2, r[-1] + (r[-1] - r[-2]) / 2, len(lats) + 1)

    theta_grid, r_grid = np.meshgrid(theta_edges, r_edges)

    im = ax.pcolormesh(theta_grid, r_grid, risk_class, cmap="RdYlGn_r", vmin=0, vmax=3, shading="flat")

    # Legend
    patches = [mpatches.Patch(color=RISK_COLORS[i], label=RISK_LABELS[i]) for i in range(4)]
    ax.legend(handles=patches, loc="lower right", fontsize=10, framealpha=0.9)

    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_yticklabels([])
    ax.set_xticklabels([])

    plt.tight_layout()
    plt.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close()

    return save_path


def plot_component_layer(layer_array, grid_lats, grid_lons, name, save_path, vmin=0, vmax=1):
    """Plot a single risk component layer.

    Args:
        layer_array: 2D risk array.
        grid_lats: latitude array.
        grid_lons: longitude array.
        name: layer name for title.
        save_path: output path.
        vmin, vmax: color range.

    Returns:
        str: path to saved file.
    """
    fig, ax = plt.subplots(1, 1, figsize=(12, 8), subplot_kw={"projection": "polar"})

    theta = np.radians(grid_lons)
    r = 90 - grid_lats

    theta_edges = np.linspace(theta[0] - np.radians(3), theta[-1] + np.radians(3), len(grid_lons) + 1)
    r_edges = np.linspace(r[0] - (r[1] - r[0]) / 2, r[-1] + (r[-1] - r[-2]) / 2, len(grid_lats) + 1)

    theta_grid, r_grid = np.meshgrid(theta_edges, r_edges)

    im = ax.pcolormesh(theta_grid, r_grid, layer_array, cmap="YlOrRd", vmin=vmin, vmax=vmax, shading="flat")
    plt.colorbar(im, ax=ax, shrink=0.7, label="Risk (0-1)")

    ax.set_title(f"{name} Risk Layer", fontsize=13, fontweight="bold", pad=20)
    ax.set_yticklabels([])
    ax.set_xticklabels([])

    plt.tight_layout()
    plt.savefig(save_path, dpi=100, bbox_inches="tight")
    plt.close()

    return save_path
