#pragma once
namespace mc_inventory_ui {
bool Busy();
// Invalidate before starting another bridge mutation, even if its worker finishes within one frame.
void RequireConfirmation();
// Call every frame, including when the F8 panel is closed. Only the open panel polls the catalog.
void Tick(bool pollCatalog, bool otherBusy = false);
// Mouse-only selection while the existing menu is open; no inputs while it is closed.
void DrawHotbar(bool interactive, bool otherBusy = false);
void Draw(bool otherBusy = false);
}
