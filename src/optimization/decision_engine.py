"""Navigation Decision Engine (DEPRECATED / PROTOTYPE).

NOTE: Retained for backwards compatibility. The AUTHORITATIVE production routing pipeline is
src.optimization.polar_routing_engine.PolarRoutingEngine.
"""
import time, logging, uuid, numpy as np
from dataclasses import dataclass, field
from typing import Optional
from src.optimization.cost_function import compute_risk_exposure, compute_sic_exposure, compute_iceberg_exposure, haversine_km
from src.optimization.route_optimizer import generate_candidate_routes, generate_baseline_route, compare_routes
logger = logging.getLogger("polarnav.decision")

@dataclass
class NavigationRequest:
    vessel_id: str = ""; vessel_name: str = ""; vessel_type: str = "Research Vessel"
    start_lat: float = 0.0; start_lon: float = 0.0; dest_lat: float = 0.0; dest_lon: float = 0.0
    cruising_speed_kn: float = 12.0; risk_tolerance: float = 0.7
    optimization_weights: Optional[dict] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    def validate(self):
        errors = []
        if not (-90 <= self.start_lat <= 90): errors.append("Invalid start_lat")
        if not (-180 <= self.start_lon <= 180): errors.append("Invalid start_lon")
        if not (-90 <= self.dest_lat <= 90): errors.append("Invalid dest_lat")
        if not (-180 <= self.dest_lon <= 180): errors.append("Invalid dest_lon")
        if self.cruising_speed_kn <= 0: errors.append("Invalid speed")
        if not (0 <= self.risk_tolerance <= 1): errors.append("Invalid risk_tolerance")
        if haversine_km(self.start_lat, self.start_lon, self.dest_lat, self.dest_lon) < 1: errors.append("Too close")
        return len(errors) == 0, errors
    @classmethod
    def from_dict(cls, d):
        return cls(vessel_id=d.get("vessel_id",""), vessel_name=d.get("vessel_name",""),
                   vessel_type=d.get("vessel_type","Research Vessel"),
                   start_lat=d.get("start_lat",0), start_lon=d.get("start_lon",0),
                   dest_lat=d.get("dest_lat",0), dest_lon=d.get("dest_lon",0),
                   cruising_speed_kn=d.get("cruising_speed_kn",12),
                   risk_tolerance=d.get("risk_tolerance",0.7),
                   optimization_weights=d.get("optimization_weights"))

def compute_temporal_cost(route_coords, risk_dataset, vessel_speed_kn=12):
    if not route_coords or len(route_coords) < 2: return {"temporal_risk": 0.0, "uncertainty_factor": 1.0}
    lats, lons, rv = risk_dataset.lat.values, risk_dataset.lon.values, risk_dataset["total_risk"].values
    cum, tr = 0, []
    for k in range(len(route_coords)-1):
        cum += haversine_km(route_coords[k][0], route_coords[k][1], route_coords[k+1][0], route_coords[k+1][1])
        i = min(max(int(np.argmin(np.abs(lats-route_coords[k][0]))),0), len(lats)-1)
        j = min(max(int(np.argmin(np.abs(lons-route_coords[k][1]))),0), len(lons)-1)
        tr.append(float(rv[i,j]) * (1.0 + (cum/1000.0)*0.05))
    return {"temporal_risk": round(float(np.mean(tr)),4) if tr else 0.0, "uncertainty_factor": round(1.0+(cum/1000.0)*0.05,3)}

def validate_route_full(route_coords, risk_dataset, vessel):
    checks = {}
    if not route_coords or len(route_coords)<2: return {"valid":False,"checks":{"has_coords":False},"message":"No route"}
    checks["valid_lats"]=all(-90<=c[0]<=90 for c in route_coords)
    checks["valid_lons"]=all(-180<=c[1]<=180 for c in route_coords)
    s,d=vessel.get("start",{}),vessel.get("destination",{})
    checks["start_valid"]=haversine_km(route_coords[0][0],route_coords[0][1],s.get("lat",0),s.get("lon",0))<150
    checks["destination_valid"]=haversine_km(route_coords[-1][0],route_coords[-1][1],d.get("lat",0),d.get("lon",0))<150
    nl,ns,tr=risk_dataset.lat.values,risk_dataset.lon.values,risk_dataset["total_risk"].values
    th=vessel.get("risk_tolerance",0.7)+0.25; bl=0
    for lat,lon in route_coords:
        ii=min(max(int(np.argmin(np.abs(nl-lat))),0),len(nl)-1)
        jj=min(max(int(np.argmin(np.abs(ns-lon))),0),len(ns)-1)
        if tr[ii,jj]>=th: bl+=1
    checks["navigable"]=bl==0
    rm=compute_risk_exposure(route_coords,risk_dataset)
    checks["max_risk_acceptable"]=rm["maximum_risk"]<0.95
    mj=max(haversine_km(route_coords[k][0],route_coords[k][1],route_coords[k+1][0],route_coords[k+1][1]) for k in range(len(route_coords)-1))
    checks["geometry_valid"]=mj<500
    ap=all(checks.values())
    return {"valid":ap,"checks":checks,"message":"Route valid" if ap else "Failed"}

def handle_route_failure(start, destination, risk_dataset, icebergs=None):
    reasons=[]; lats,lons=risk_dataset.lat.values,risk_dataset.lon.values; risk=risk_dataset["total_risk"].values
    si=min(max(int(np.argmin(np.abs(lats-start["lat"]))),0),len(lats)-1)
    sj=min(max(int(np.argmin(np.abs(lons-start["lon"]))),0),len(lons)-1)
    if risk[si,sj]>0.9: reasons.append("Start in critical-risk area")
    gi=min(max(int(np.argmin(np.abs(lats-destination["lat"]))),0),len(lats)-1)
    gj=min(max(int(np.argmin(np.abs(lons-destination["lon"]))),0),len(lons)-1)
    if risk[gi,gj]>0.9: reasons.append("Destination in critical-risk area")
    hp=float(np.mean(risk>0.7))
    if hp>0.5: reasons.append(f"{hp*100:.0f}% area has high risk")
    if not reasons: reasons.append("No path within risk constraints")
    return {"status":"NO_SAFE_ROUTE_FOUND","reasons":reasons,"start_risk":round(float(risk[si,sj]),4),"destination_risk":round(float(risk[gi,gj]),4),"high_risk_area_percent":round(hp*100,1)}

def explain_route(candidate, baseline=None):
    codes,expls=[],[]; risk=candidate.get("average_risk",0); sic=candidate.get("sea_ice_exposure",{}).get("average_sic",0); ibm=candidate.get("iceberg_exposure",{}).get("min_distance_km",9999)
    if risk<0.25: codes.append("LOW_RISK_SELECTED"); expls.append("Route maintains low risk")
    elif risk<0.50: codes.append("MODERATE_RISK_ACCEPTED"); expls.append("Moderate risk for better distance")
    if sic>0.3: codes.append("AVOIDED_HIGH_SIC"); expls.append("Avoids high sea-ice")
    if ibm<100: codes.append("AVOIDED_ICEBERG_CORRIDOR"); expls.append(f"{ibm:.0f} km iceberg separation")
    if baseline and baseline.get("found"):
        bd=baseline.get("distance_km",0); od=candidate.get("distance_km",0)
        if od>bd*1.05: codes.append("DISTANCE_PENALTY_ACCEPTED"); expls.append(f"Adds {((od-bd)/bd)*100:.1f}% distance for safety")
    if not codes: codes.append("STANDARD_OPTIMIZATION"); expls.append("Standard criteria")
    return {"reason_codes":codes,"explanation":". ".join(expls)+"."}

def execute_navigation_decision(request, risk_dataset, sic_dataset=None, icebergs=None):
    t0=time.time(); valid,errors=request.validate()
    if not valid: return {"status":"ERROR","errors":errors,"request_id":request.request_id}
    v={"id":request.vessel_id,"name":request.vessel_name,"type":request.vessel_type,
       "start":{"lat":request.start_lat,"lon":request.start_lon},
       "destination":{"lat":request.dest_lat,"lon":request.dest_lon},
       "cruising_speed_kn":request.cruising_speed_kn,"risk_tolerance":request.risk_tolerance}
    opt=generate_candidate_routes(v,risk_dataset,sic_dataset,icebergs,request.optimization_weights)
    if not opt["candidates"]:
        f=handle_route_failure(v["start"],v["destination"],risk_dataset,icebergs)
        el=round(time.time()-t0,3)
        return {"status":"NO_SAFE_ROUTE_FOUND","request_id":request.request_id,"failure":f,"computation_time_ms":round(el*1000,1)}
    bl=generate_baseline_route(v,risk_dataset); rec=opt["recommended"]
    tmp=compute_temporal_cost(rec["coordinates"],risk_dataset,request.cruising_speed_kn)
    val=validate_route_full(rec["coordinates"],risk_dataset,v)
    exp=explain_route(rec,bl)
    cmp=compare_routes(rec,bl) if bl.get("found") else {}
    el=round(time.time()-t0,3)
    alts=[c for c in opt["candidates"] if c["route_id"]!=rec["route_id"]]
    return {
        "status":"success","request_id":request.request_id,
        "selected_vessel":{"id":request.vessel_id,"latitude":request.start_lat,"longitude":request.start_lon},
        "destination":{"latitude":request.dest_lat,"longitude":request.dest_lon},
        "recommended_route":{"route_id":rec["route_id"],"coordinates":rec["coordinates"],
            "distance_km":rec["distance_km"],"travel_time_hours":rec["travel_time_hours"],
            "average_risk":rec["average_risk"],"maximum_risk":rec["maximum_risk"],
            "sea_ice_exposure":rec["sea_ice_exposure"],"iceberg_exposure":rec["iceberg_exposure"],
            "relative_fuel_cost":rec["relative_fuel_cost"],"total_cost":rec["total_cost"],
            "quality_score":rec["quality_score"],"waypoints":rec["waypoints"]},
        "alternatives":[{"route_id":c["route_id"],"profile":c["profile"],"distance_km":c["distance_km"],
            "travel_time_hours":c["travel_time_hours"],"average_risk":c["average_risk"],
            "quality_score":c["quality_score"],"relative_fuel_cost":c["relative_fuel_cost"],
            "coordinates":c["coordinates"]} for c in alts],
        "baseline":bl if bl.get("found") else None,"comparison":cmp,
        "temporal_routing":tmp,"validation":val,"explanation":exp,
        "optimization":{"objective":"multi-objective weighted cost minimization",
            "weights":opt["candidates"][0]["component_costs"] if opt["candidates"] else {},
            "profiles_used":opt["profiles_used"]},
        "computation_time_ms":round(el*1000,1),
    }
