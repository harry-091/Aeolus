"""A* pathfinding on the navigation grid.

Uses Phase 4 risk as movement cost.
"""
import heapq
import numpy as np
from src.navigation.grid import get_neighbors, cell_distance


def a_star(nav_grid, start_idx, goal_idx, risk_weight=1.0):
    """A* pathfinding on the navigation grid.

    Args:
        nav_grid: xr.Dataset with nav_grid and risk.
        start_idx: (lat_idx, lon_idx) tuple.
        goal_idx: (lat_idx, lon_idx) tuple.
        risk_weight: weight of risk in path cost (0=pure distance, higher=risk-averse).

    Returns:
        dict with route_indices, route_coords, total_distance_km,
        total_risk_cost, waypoints.
    """
    lats = nav_grid.lat.values
    lons = nav_grid.lon.values
    grid = nav_grid["nav_grid"].values
    risk = nav_grid["risk"].values
    n_lat, n_lon = grid.shape

    si, sj = start_idx
    gi, gj = goal_idx

    # Validate start and goal
    if grid[si, sj] == 0:
        return {"found": False, "reason": "Start cell is blocked"}
    if grid[gi, gj] == 0:
        return {"found": False, "reason": "Goal cell is blocked"}

    # A* implementation
    open_set = []
    heapq.heappush(open_set, (0, si, sj))
    came_from = {}
    g_score = {(si, sj): 0}
    closed = set()

    while open_set:
        _, ci, cj = heapq.heappop(open_set)

        if (ci, cj) == (gi, gj):
            # Reconstruct path
            path = []
            current = (gi, gj)
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append((si, sj))
            path.reverse()

            # Calculate metrics
            total_dist = 0
            total_risk = 0
            for k in range(len(path) - 1):
                i1, j1 = path[k]
                i2, j2 = path[k + 1]
                total_dist += cell_distance(lats[i1], lons[j1], lats[i2], lons[j2])
                total_risk += risk[i2, j2]

            coords = [(float(lats[i]), float(lons[j])) for i, j in path]

            return {
                "found": True,
                "route_indices": path,
                "route_coords": coords,
                "total_distance_km": round(total_dist, 2),
                "total_risk_cost": round(float(total_risk), 4),
                "waypoints": len(path),
            }

        if (ci, cj) in closed:
            continue
        closed.add((ci, cj))

        for ni, nj in get_neighbors(ci, cj, n_lat, n_lon):
            if (ni, nj) in closed or grid[ni, nj] == 0:
                continue

            dist = cell_distance(lats[ci], lons[cj], lats[ni], lons[nj])
            move_cost = dist + risk_weight * risk[ni, nj] * dist
            tentative_g = g_score[(ci, cj)] + move_cost

            if tentative_g < g_score.get((ni, nj), float("inf")):
                came_from[(ni, nj)] = (ci, cj)
                g_score[(ni, nj)] = tentative_g
                h = cell_distance(lats[ni], lons[nj], lats[gi], lons[gj])
                f = tentative_g + h
                heapq.heappush(open_set, (f, ni, nj))

    return {"found": False, "reason": "No path found"}
