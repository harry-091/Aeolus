"""Convert point-based SIC/risk data into grid cell polygons for deck.gl GridCellLayer."""
import json
import os

def points_to_grid_cells(points, lats, lons, value_key='value'):
    """Convert [lat, lon, value] points into grid cell polygons.
    
    Each point becomes a polygon with 4 corners based on grid spacing.
    """
    if len(lats) < 2 or len(lons) < 2:
        return []
    
    dlat = abs(lats[1] - lats[0]) / 2
    dlon = abs(lons[1] - lons[0]) / 2
    
    cells = []
    for p in points:
        lat, lon, val = p[0], p[1], p[2]
        # Skip near-zero values to reduce clutter
        if val < 0.01:
            continue
        # 4 corners of the cell: [lon, lat] format for deck.gl
        polygon = [
            [lon - dlon, lat - dlat],
            [lon + dlon, lat - dlat],
            [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat],
        ]
        cells.append({
            'polygon': polygon,
            'value': val,
            'lat': lat,
            'lon': lon,
        })
    return cells


def process_all():
    vdir = 'data/processed/verification'
    outdir = 'data/processed/verification'
    os.makedirs(outdir, exist_ok=True)
    
    # Process SIC
    sic = json.load(open(os.path.join(vdir, 'phase2_sic.json')))
    sic_cells = points_to_grid_cells(sic['current_points'], sic['lats'], sic['lons'])
    with open(os.path.join(outdir, 'sic_cells.json'), 'w') as f:
        json.dump({'cells': sic_cells, 'lat_range': [sic['lats'][0], sic['lats'][-1]], 'lon_range': [sic['lons'][0], sic['lons'][-1]]}, f)
    print(f'SIC cells: {len(sic_cells)}')
    
    # Process forecast SIC
    if 'forecast_points' in sic:
        fc_cells = points_to_grid_cells(sic['forecast_points'], sic['lats'], sic['lons'])
        with open(os.path.join(outdir, 'forecast_cells.json'), 'w') as f:
            json.dump({'cells': fc_cells}, f)
        print(f'Forecast cells: {len(fc_cells)}')
    
    # Process risk
    risk = json.load(open(os.path.join(vdir, 'phase4_risk.json')))
    risk_cells = points_to_grid_cells(risk['risk_points'], risk['lats'], risk['lons'])
    with open(os.path.join(outdir, 'risk_cells.json'), 'w') as f:
        json.dump({'cells': risk_cells}, f)
    print(f'Risk cells: {len(risk_cells)}')
    
    print('Grid cell preprocessing complete')


if __name__ == '__main__':
    process_all()
