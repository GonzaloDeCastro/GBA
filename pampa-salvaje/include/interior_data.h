// Generado por tools/gen_assets.py. No editar a mano.
#ifndef INTERIOR_DATA_H
#define INTERIOR_DATA_H

namespace interior
{
    // 0 piso, 1 bloqueado, 2 mostrador (se puede hablar a traves), 3 salida
    inline constexpr int width = 15;
    inline constexpr int height = 10;
    // el casillero (0,0) esta en la pantalla en (-120,-80)
    inline constexpr unsigned char house_grid[150] = {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0,1,0,0,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1};
    inline constexpr int house_npc_x = 6;
    inline constexpr int house_npc_y = 4;
    inline constexpr unsigned char vet_grid[150] = {1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,1,0,0,0,1,1,1,1,1,1,1,0,0,2,2,2,2,2,0,0,1,1,1,1,1,1,0,0,0,0,0,0,0,1,0,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1};
    inline constexpr int vet_npc_x = 7;
    inline constexpr int vet_npc_y = 3;
    inline constexpr int spawn_x = 7;
    inline constexpr int spawn_y = 7;
}

#endif
