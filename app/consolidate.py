from fastapi import APIRouter, HTTPException
from typing import List
import os, uuid
from utils.helpers import load_data, save_data

router = APIRouter()

DATA_DIR = "data"
HYPERVISOR_FILE = os.path.join(DATA_DIR, "hypervisors.json")
PLAN_FILE = os.path.join(DATA_DIR, "consolidate_plans.json")  # planları saklamak için
FLAVOR_FILE = os.path.join(DATA_DIR, "flavors.json")

# ----------------------------
# CONSOLIDATE MODELS
# ----------------------------
class PlanCreateRequest(BaseModel):
    hypervisors: List[str] 
    migration_order: Optional[str] = "smaller_first"
    max_concurrent_migration_per_hypervisor: Optional[int] = 1

class PlanApplyRequest(BaseModel):
    plan_id: str

class PlanStatusResponse(BaseModel):
    plan_id: str
    completed_percentage: float
    drained_hypervisors: List[str]
    remaining_steps: List[List[str]]

# ----------------------------
# CREATE PLAN
# ----------------------------
@router.post("/api/consolidate/plan/create")
def consolidate_plan_create(body: PlanCreateRequest):
    hypervisors = load_data(HYPERVISOR_FILE)
    flavors = load_data(FLAVOR_FILE)

    requested_hv = body.hypervisors
    migration_order = body.migration_order
    max_concurrent = body.max_concurrent_migration_per_hypervisor

    # Tüm VMs’i topla
    vms_to_move = []
    for hv_name in requested_hv:
        hv = next((h for h in hypervisors if h["hypervisor_name"] == hv_name), None)
        if hv:
            for vm in hv.get("vms", []):
                # VM ve boyutu
                flavor = next((f for f in flavors if f["flavor_name"] == vm["vm_flavor"]), None)
                size = flavor["cpu"] + flavor["memory"] + flavor["disk"] if flavor else 0
                vms_to_move.append({"vm_name": vm["vm_name"], "size": size})

    # Smaller-first / Larger-first
    reverse = migration_order == "larger-first"
    vms_to_move.sort(key=lambda x: x["size"], reverse=reverse)

    # Step wise batching
    steps = [ [vm["vm_name"] for vm in vms_to_move[i:i+max_concurrent]] 
              for i in range(0, len(vms_to_move), max_concurrent) ]

    # Plan ID oluştur
    plan_id = str(uuid.uuid4())
    plan_entry = {
        "plan_id": plan_id,
        "steps": steps,
        "remaining_steps": steps.copy()
    }

    # Planı kaydet
    plans = load_data(PLAN_FILE) if os.path.exists(PLAN_FILE) else []
    plans.append(plan_entry)
    save_data(PLAN_FILE, plans)

    return {"plan_id": plan_id, "plan": steps}

# ----------------------------
# APPLY PLAN
# ----------------------------
@router.post("/api/consolidate/plan/apply")
def consolidate_plan_apply(body: PlanApplyRequest):
    plan_id = body.plan_id
    hypervisors = load_data(HYPERVISOR_FILE)
    plans = load_data(PLAN_FILE) if os.path.exists(PLAN_FILE) else []

    plan_entry = next((p for p in plans if p["plan_id"] == plan_id), None)
    if not plan_entry:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Dummy apply: tüm remaining_steps'i diğer hypervisor'a taşı
    for step in plan_entry["remaining_steps"]:
        for vm_name in step:
            for hv in hypervisors:
                for vm in hv.get("vms", []):
                    if vm["vm_name"] == vm_name:
                        target_hv = next((h for h in hypervisors if h["hypervisor_name"] != hv["hypervisor_name"]), None)
                        if target_hv:
                            hv["vms"].remove(vm)
                            target_hv.setdefault("vms", []).append(vm)
                        break

    # Plan update
    plan_entry["remaining_steps"] = []
    save_data(HYPERVISOR_FILE, hypervisors)
    save_data(PLAN_FILE, plans)

    return {"message": f"Plan {plan_id} applied successfully", "plan_id": plan_id}

# ----------------------------
# LIST PLANS
# ----------------------------
@router.get("/api/consolidate/list/plans")
def consolidate_list_plans():
    plans = load_data(PLAN_FILE) if os.path.exists(PLAN_FILE) else []
    return {"plans": [{"plan_id": p["plan_id"]} for p in plans]}

# ----------------------------
# RETRIEVE PLAN
# ----------------------------
@router.get("/api/consolidate/retrieve/plan")
def consolidate_retrieve_plan(plan_id: str):
    plans = load_data(PLAN_FILE) if os.path.exists(PLAN_FILE) else []
    plan_entry = next((p for p in plans if p["plan_id"] == plan_id), None)
    if not plan_entry:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": plan_entry}

# ----------------------------
# STATUS PLAN
# ----------------------------
@router.get("/api/consolidate/status/plan")
def consolidate_status_plan(plan_id: str):
    plans = load_data(PLAN_FILE) if os.path.exists(PLAN_FILE) else []
    hypervisors = load_data(HYPERVISOR_FILE)

    plan_entry = next((p for p in plans if p["plan_id"] == plan_id), None)
    if not plan_entry:
        raise HTTPException(status_code=404, detail="Plan not found")

    total_steps = len(plan_entry.get("steps", []))
    remaining_steps = plan_entry.get("remaining_steps", [])
    completed_steps = total_steps - len(remaining_steps)
    percent_complete = int((completed_steps / total_steps) * 100) if total_steps > 0 else 100

    drained_hvs = [hv for hv in hypervisors if len(hv.get("vms", [])) == 0]

    return {
        "message": f"{percent_complete}% completed of plan {plan_id}, {len(drained_hvs)} hypervisors are drained",
        "remaining_steps": remaining_steps
    }
