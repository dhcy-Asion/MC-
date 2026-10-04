"""Exercise the native panel's bounded decoder without launching either game."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path("C:/msys64/ucrt64/bin/g++.exe")
SOURCE = r'''
#include "mc_inventory_protocol.h"
#include <cassert>
#include <iostream>
using namespace mc_inventory;
std::string inventory() {
    std::string out = "inventory\t9\t1\n";
    for (int n=0;n<36;++n) out += "slot\t" + std::to_string(n) +
        (n==1 ? "\tminecraft:ender_pearl\t16\t16\tEnder Pearl\n" : "\t-\t0\t0\t\n");
    return out;
}
int main() {
    uint64_t number=0;
    assert(Number("9223372036854775807",INT64_MAX,number));
    assert(!Number("9223372036854775808",INT64_MAX,number));
    assert(!Number("-1",35,number)); assert(!Number("1.0",35,number));
    assert(!Number("36",35,number)); assert(!Number("18446744073709551616",UINT64_MAX,number));
    Inventory inv;
    assert(ParseInventory(inventory(),inv) && inv.selected==1 && inv.slots[1].count==16);
    assert(inv.slots[0].id.empty());
    auto bad=inventory(); bad.erase(bad.find("slot\t35"));
    assert(!ParseInventory(bad,inv) && inv.slots[1].count==16); // failure is atomic
    bad=inventory(); bad.replace(bad.find("slot\t35"),7,"slot\t34");
    assert(!ParseInventory(bad,inv)); // duplicate/missing slot
    bad=inventory(); bad.replace(bad.find("\t16\t16"),6,"\t17\t16");
    assert(!ParseInventory(bad,inv)); // count exceeds vanilla maximum
    bad=inventory(); bad.replace(bad.find("\t-\t0\t0"),6,"\t-\t1\t0");
    assert(!ParseInventory(bad,inv)); // empty slot has no residual item
    bad=inventory(); bad.replace(0,13,"inventory\t9\t36");
    assert(!ParseInventory(bad,inv));
    assert(!ParseInventory(std::string(65537,'x'),inv));
    Catalog cat;
    assert(ParseCatalog("catalog\t2\t0\t1\nitem\tminecraft:stone\tStone\t64\t1\t1\n",cat));
    assert(cat.next==1 && cat.items[0].maxCount==64);
    assert(ParseCatalog("catalog\t2\t1\t-1\nitem\tminecraft:bow\tBow\t1\t0\t0\n",cat));
    assert(!cat.items[0].placeSupported && !cat.items[0].isBlock);
    assert(ParseCatalog("catalog\t0\t0\t-1\n",cat) && cat.items.empty());
    assert(!ParseCatalog("catalog\t2\t0\t-1\n",cat)); // incomplete page
    assert(!ParseCatalog("catalog\t2\t3\t-1\n",cat));
    assert(!ParseCatalog("catalog\t1\t0\t-1\nitem\tminecraft:bow\tBow\t0\t0\t0\n",cat));
    assert(!ParseCatalog("catalog\t1\t0\t-1\nitem\tminecraft:bow\tBow\t1\t2\t0\n",cat));
    assert(!ParseCatalog("catalog\t1\t0\t-1\nitem\tbad\tBow\t1\t0\t0\n",cat));
    assert(!ParseCatalog("catalog\t2\t0\t-1\nitem\tminecraft:bow\tBow\t1\t0\t0\n"
                        "item\tminecraft:bow\tBow\t1\t0\t0\n",cat));
    assert(!ParseCatalog("catalog\t1\t0\t-1\nitem\tminecraft:bow\tBow\t1\t0\n",cat));
    std::cout << "Native inventory decoder checks passed: valid pages/slots, bounds, malformed/truncated responses, atomic rejection\n";
}
'''

def main():
    if not COMPILER.is_file():
        raise RuntimeError("Install the project's MSYS2 UCRT64 compiler before this check")
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="inventory-ui-check-", dir=ROOT / "build") as directory:
        directory = Path(directory)
        source, output = directory / "check.cpp", directory / "check.exe"
        source.write_text(SOURCE, encoding="utf-8")
        subprocess.run([str(COMPILER), "-std=c++17", "-static", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "red-side-patches"), str(source), "-o", str(output)], check=True)
        subprocess.run([str(output)], check=True)

if __name__ == "__main__":
    main()
