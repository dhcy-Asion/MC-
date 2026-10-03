"""Integration checks against the running, real Minecraft authority."""
from pathlib import Path
import json
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]


def call(path="state", body=None):
    data=None if body is None else json.dumps(body).encode()
    req=Request("http://127.0.0.1:8766/api/"+path,data=data,headers={"Content-Type":"application/json"})
    with urlopen(req,timeout=8) as response:
        return json.load(response)


def mutate(path, **body):
    return call(path,{"operationId":str(uuid.uuid4()),**body})


def check_delta(before, after, expected):
    keys=set(before["inventory"])|set(after["inventory"])
    delta={k:after["inventory"].get(k,0)-before["inventory"].get(k,0) for k in keys}
    delta={k:v for k,v in delta.items() if v}
    assert delta==expected,(delta,expected)


def main():
    evidence={"before":call(),"checks":[]}
    initial=evidence["before"]
    assert initial["engine"]=="Minecraft Java 1.21.1"
    assert initial["inventory"].get("minecraft:oak_log",0)>=2,"Two oak logs required"
    first=mutate("craft",recipe="minecraft:oak_planks")
    check_delta(initial,first,{"minecraft:oak_log":-1,"minecraft:oak_planks":4})
    evidence["checks"].append("vanilla oak_planks recipe: 1 log -> 4 planks")
    request={"operationId":str(uuid.uuid4()),"recipe":"minecraft:oak_planks"}
    second=call("craft",request)
    repeated=call("craft",request)
    assert second==repeated,"Repeated operation consumed materials again"
    check_delta(first,second,{"minecraft:oak_log":-1,"minecraft:oak_planks":4})
    evidence["checks"].append("retrying identical operation ID does not duplicate crafting")
    sticks=mutate("craft",recipe="minecraft:stick")
    check_delta(second,sticks,{"minecraft:oak_planks":-2,"minecraft:stick":4})
    table=mutate("craft",recipe="minecraft:crafting_table")
    check_delta(sticks,table,{"minecraft:oak_planks":-4,"minecraft:crafting_table":1})
    evidence["checks"].append("vanilla shaped stick and crafting_table recipes")
    # This corner is away from the user-facing build cells, and is removed below.
    pos={"x":16,"y":95,"z":16}
    assert not any(all(b[a]==pos[a] for a in "xyz") for b in table["blocks"]),"Test corner is occupied"
    placed=mutate("place",block="minecraft:oak_planks",**pos)
    check_delta(table,placed,{"minecraft:oak_planks":-1})
    assert any(all(b[a]==pos[a] for a in "xyz") for b in placed["blocks"])
    broken=mutate("break",**pos)
    check_delta(placed,broken,{"minecraft:oak_planks":1})
    assert not any(all(b[a]==pos[a] for a in "xyz") for b in broken["blocks"])
    evidence["checks"].append("real MC world placement consumes item; native loot restores plank on break")
    before_failed=call()
    # Rejecting an unknown recipe must leave the state unchanged.
    try:
        mutate("craft",recipe="minecraft:invalid_prototype_recipe")
        raise AssertionError("Unknown recipe was accepted")
    except HTTPError as error:
        assert error.code==400
    assert call()==before_failed,"Rejected recipe changed state"
    evidence["checks"].append("rejected recipe leaves inventory, blocks and revision unchanged")
    # Default starter inventory ends with two planks; insufficient crafting must roll back.
    if before_failed["inventory"].get("minecraft:oak_planks",0)<4:
        try:
            mutate("craft",recipe="minecraft:crafting_table")
            raise AssertionError("Insufficient-material recipe was accepted")
        except HTTPError as error:
            assert error.code==400
        assert call()==before_failed,"Partial ingredient consumption was not rolled back"
        evidence["checks"].append("insufficient materials roll back partially consumed ingredients")
    evidence["after"]=call()
    (ROOT/"runtime/authority-checks.json").write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))


if __name__=="__main__":main()
