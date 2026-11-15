// PAMPA SALVAJE - prototipo jugable (GBA, Butano)
// Recorre una Argentina estilizada, habla con la gente, entra a las casas y arma tu equipo de fauna autoctona.

#include "bn_core.h"
#include "bn_keypad.h"
#include "bn_random.h"
#include "bn_color.h"
#include "bn_bg_palettes.h"
#include "bn_camera_ptr.h"
#include "bn_fixed_point.h"
#include "bn_regular_bg_ptr.h"
#include "bn_sprite_ptr.h"
#include "bn_sprite_text_generator.h"
#include "bn_string.h"
#include "bn_string_view.h"
#include "bn_vector.h"
#include "bn_optional.h"

#include "common_variable_8x8_sprite_font.h"
#include "bn_regular_bg_items_world.h"
#include "bn_regular_bg_items_mapscreen.h"
#include "bn_regular_bg_items_dialog_panel.h"
#include "bn_regular_bg_items_interior_house.h"
#include "bn_regular_bg_items_interior_vet.h"
#include "bn_sprite_items_player.h"
#include "bn_sprite_items_dog.h"
#include "bn_sprite_items_marker.h"
#include "bn_sprite_items_arrow_down.h"
#include "bn_sprite_items_arrow_right.h"
#include "bn_sprite_items_npc0.h"
#include "bn_sprite_items_npc1.h"
#include "bn_sprite_items_npc2.h"
#include "bn_sprite_items_npc3.h"
#include "bn_sprite_items_npc4.h"
#include "bn_sprite_items_npc5.h"
#include "bn_sprite_items_npc6.h"
#include "bn_sprite_items_npc7.h"
#include "bn_sprite_items_npc8.h"
#include "bn_sprite_items_npc9.h"
#include "bn_sprite_items_c0.h"
#include "bn_sprite_items_c1.h"
#include "bn_sprite_items_c2.h"
#include "bn_sprite_items_c3.h"
#include "bn_sprite_items_c4.h"
#include "bn_sprite_items_c5.h"
#include "bn_sprite_items_c6.h"
#include "bn_sprite_items_c7.h"
#include "bn_sprite_items_c8.h"
#include "bn_sprite_items_c9.h"
#include "bn_sprite_items_cdog.h"
#include "bn_regular_bg_items_battle_norte.h"
#include "bn_regular_bg_items_battle_pampa.h"
#include "bn_regular_bg_items_battle_patagonia.h"
#include "bn_regular_bg_items_battle_costa.h"
#include "bn_regular_bg_items_battle_andes.h"
#include "bn_music.h"
#include "bn_math.h"
#include "bn_sprite_palette_ptr.h"
#include "bn_sprite_items_hit.h"
#include "bn_sprite_items_bolas.h"
#include "bn_sprite_items_spark.h"
#include "bn_sprite_items_hpbar.h"
#include "bn_music_items.h"
#include "world_data.h"
#include "interior_data.h"
#include "argmap_data.h"

namespace
{
    // ------------------------------------------------------------ datos
    enum Zone { NORTE, PAMPA, PATAGONIA, COSTA, ANDES, ZONE_COUNT };

    const char* const zone_names[ZONE_COUNT] = {
        "NORTE - Chaco y NOA", "PAMPA HUMEDA", "PATAGONIA", "COSTA ATLANTICA", "CORDILLERA DE LOS ANDES"
    };

    struct Species
    {
        const char* name;
        int hp;
        int atk;
    };

    constexpr int species_count = 10;      // salvajes (0..9)
    constexpr int dog_id = 10;             // Mate
    constexpr int creature_count = 11;
    const Species species[creature_count] = {
        {"Hornerito", 30, 6},   // 0  hornero
        {"Carpinchin", 40, 5},  // 1  carpincho
        {"Nandusito", 34, 7},   // 2  nandu
        {"Guanaquito", 38, 6},  // 3  guanaco
        {"Yaguarin", 46, 10},   // 4  yaguarete
        {"Zorrito", 28, 7},     // 5  zorro pampeano
        {"Pingui", 32, 5},      // 6  pinguino de Magallanes
        {"Condorcito", 44, 9},  // 7  condor andino
        {"Vizcachon", 30, 6},   // 8  vizcacha
        {"Teru", 24, 5},        // 9  tero
        {"Mate", 40, 8},        // 10 tu perrito companero
    };

    // Especies que aparecen en cada zona (ids de species[])
    constexpr int max_table = 5;
    const int encounter_table[ZONE_COUNT][max_table] = {
        {0, 1, 4, 9, 4},    // NORTE
        {0, 2, 5, 8, 9},    // PAMPA
        {2, 3, 5, 8, 3},    // PATAGONIA
        {6, 9, 6, 1, 6},    // COSTA
        {3, 7, 7, 3, 8},    // ANDES
    };

    // Debe coincidir con el orden de tools/gen_assets.py
    enum Tile : unsigned char
    {
        T_PASTO, T_ALTO, T_AGUA, T_ARBOL, T_CAMINO, T_ROCA, T_ARENA, T_ESTEPA,
        T_CASA, T_PUERTA, T_VET, T_VETPUERTA
    };

    constexpr int tile_px = 16;
    constexpr int map_half = world::width * tile_px / 2;
    constexpr int start_tx = 32;
    constexpr int start_ty = 30;
    constexpr int char_dy = 0;          // los personajes son de 16x16: ocupan exactamente un casillero
    constexpr int max_team = 6;

    // Volumen de la musica
    constexpr bn::fixed music_volume_world = 0.55;
    constexpr bn::fixed music_volume_battle = 0.65;

    // Provincia (indice en argmap::names) que corresponde a un casillero del mundo
    int province_at(int x, int y)
    {
        return argmap::province_of[y * world::width + x];
    }

    struct Member
    {
        int id = dog_id;
        int hp = 0;
    };

    struct Game
    {
        bn::random rng;
        bool captured[species_count] = {};
        bool duel_won = false;
        Member team[max_team];
        int team_size = 1;
        int tx = start_tx;
        int ty = start_ty;
        int dog_tx = start_tx - 1;     // el perrito arranca al lado tuyo
        int dog_ty = start_ty;

        Game()
        {
            team[0].id = dog_id;
            team[0].hp = species[dog_id].hp;
        }
    };

    void heal_all(Game& g)
    {
        for(int i = 0; i < g.team_size; ++i)
        {
            g.team[i].hp = species[g.team[i].id].hp;
        }
    }

    int first_alive(const Game& g)
    {
        for(int i = 0; i < g.team_size; ++i)
        {
            if(g.team[i].hp > 0)
            {
                return i;
            }
        }
        return -1;
    }

    // Sprite de cada criatura (0..9 salvajes, 10 = Mate)
    const bn::sprite_item* const creature_item[creature_count] = {
        &bn::sprite_items::c0, &bn::sprite_items::c1, &bn::sprite_items::c2, &bn::sprite_items::c3,
        &bn::sprite_items::c4, &bn::sprite_items::c5, &bn::sprite_items::c6, &bn::sprite_items::c7,
        &bn::sprite_items::c8, &bn::sprite_items::c9, &bn::sprite_items::cdog,
    };

    // Fondo de combate segun la zona (mismo orden que enum Zone)
    const bn::regular_bg_item* const battle_bg_item[5] = {
        &bn::regular_bg_items::battle_norte, &bn::regular_bg_items::battle_pampa,
        &bn::regular_bg_items::battle_patagonia, &bn::regular_bg_items::battle_costa,
        &bn::regular_bg_items::battle_andes,
    };

    // ------------------------------------------------------------ NPCs
    enum NpcKind { K_INFO, K_HEAL, K_DUEL, K_TEACH };

    struct Npc
    {
        const char* name;
        const bn::sprite_item* item;
        NpcKind kind;
    };

    // El orden coincide con NPCS en tools/gen_assets.py (posiciones en world::npc_*)
    const Npc npcs[world::npc_count] = {
        {"Don Segundo", &bn::sprite_items::npc0, K_INFO},
        {"Guardaparque Lila", &bn::sprite_items::npc1, K_HEAL},
        {"Pescador Beto", &bn::sprite_items::npc2, K_INFO},
        {"Gaucho Tomas", &bn::sprite_items::npc3, K_DUEL},
        {"Profe Ana", &bn::sprite_items::npc4, K_TEACH},
        {"Wara", &bn::sprite_items::npc5, K_HEAL},
    };

    // Gente que vive en las casas y la veterinaria
    const Npc vet_npc = {"Dra. Lucia", &bn::sprite_items::npc6, K_HEAL};
    constexpr int resident_count = 3;
    const Npc residents[resident_count] = {
        {"Abuela Rosa", &bn::sprite_items::npc7, K_INFO},
        {"Tomi", &bn::sprite_items::npc8, K_INFO},
        {"Don Anselmo", &bn::sprite_items::npc9, K_INFO},
    };

    int npc_at(int x, int y)
    {
        for(int i = 0; i < world::npc_count; ++i)
        {
            if(world::npc_tx[i] == x && world::npc_ty[i] == y)
            {
                return i;
            }
        }
        return -1;
    }

    Tile tile_at(int x, int y)
    {
        if(x < 0 || y < 0 || x >= world::width || y >= world::height)
        {
            return T_ROCA;
        }
        return Tile(world::tiles[y * world::width + x]);
    }

    bool walkable(int x, int y)
    {
        Tile t = tile_at(x, y);
        return t != T_AGUA && t != T_ARBOL && t != T_ROCA && t != T_CASA && t != T_VET && npc_at(x, y) < 0;
    }

    bool tall_grass(Tile t) { return t == T_ALTO || t == T_ESTEPA; }

    Zone zone_at(int x, int y)
    {
        if(x <= 9) return ANDES;
        if(x >= 54) return COSTA;
        if(y < 22) return NORTE;
        if(y < 44) return PAMPA;
        return PATAGONIA;
    }

    bn::fixed_point tile_center(int x, int y)
    {
        return bn::fixed_point(x * tile_px + tile_px / 2 - map_half, y * tile_px + tile_px / 2 - map_half);
    }

    // La GBA permite 128 sprites en total y cada letra usa uno: mantener los textos cortos.
    using text_lines = bn::vector<bn::sprite_ptr, 110>;

    const bn::color backdrop_world(8, 18, 12);
    const bn::color backdrop_dark(4, 6, 14);

    void say(bn::sprite_text_generator& gen, text_lines& out, int x, int y, const bn::string_view& s)
    {
        gen.generate(x, y, s, out);
    }

    // A o ENTER (START) confirman en todos los menus y dialogos
    bool confirm()
    {
        return bn::keypad::a_pressed() || bn::keypad::start_pressed();
    }

    // Muestra un mensaje en el cuadro inferior de combate y espera A / Enter (con flechita).
    void message(bn::sprite_text_generator& gen, const bn::string_view& line1, const bn::string_view& line2 = "")
    {
        text_lines t;
        say(gen, t, -110, 49, line1);
        say(gen, t, -110, 63, line2);
        bn::sprite_ptr arrow = bn::sprite_items::arrow_down.create_sprite(106, 72);
        int blink = 0;
        while(true)
        {
            arrow.set_visible((blink++ / 20) % 2 == 0);
            bn::core::update();
            if(confirm())
            {
                break;
            }
        }
    }

    // ------------------------------------------------------------ cuadro de dialogo
    class DialogBox
    {
    public:
        DialogBox(bn::sprite_text_generator& gen, const char* name) :
            _gen(gen),
            _panel(bn::regular_bg_items::dialog_panel.create_bg(0, 0)),
            _arrow(bn::sprite_items::arrow_down.create_sprite(108, 73)),
            _cursor(bn::sprite_items::arrow_right.create_sprite(-104, 57))
        {
            _panel.set_priority(2);
            _arrow.set_visible(false);
            _cursor.set_visible(false);
            say(_gen, _name, -112, 31, name);
        }

        // Pagina de 2 lineas con efecto maquina de escribir; A / Enter la completa y luego avanza.
        void page(const char* l1, const char* l2 = "")
        {
            const int len1 = int(bn::string_view(l1).size());
            const int len2 = int(bn::string_view(l2).size());
            const int total = len1 + len2;
            int shown = 0;
            int blink = 0;
            text_lines t;

            auto render = [&]()
            {
                t.clear();
                say(_gen, t, -110, 47, bn::string_view(l1, shown < len1 ? shown : len1));
                if(shown > len1)
                {
                    say(_gen, t, -110, 61, bn::string_view(l2, shown - len1));
                }
            };

            while(true)
            {
                if(shown < total)
                {
                    shown += 2;
                    if(shown > total) shown = total;
                    render();
                    _arrow.set_visible(false);
                }
                else
                {
                    _arrow.set_visible((blink++ / 20) % 2 == 0);
                }
                bn::core::update();
                if(confirm())
                {
                    if(shown < total)
                    {
                        shown = total;
                        render();
                    }
                    else
                    {
                        break;
                    }
                }
            }
            _arrow.set_visible(false);
        }

        // Pregunta con dos opciones y una flechita: arriba/abajo mueven, A o Enter confirman.
        int choose(const char* prompt, const char* option0, const char* option1)
        {
            text_lines t;
            say(_gen, t, -108, 45, prompt);
            say(_gen, t, -92, 57, option0);
            say(_gen, t, -92, 69, option1);
            _cursor.set_visible(true);
            int sel = 0;
            int blink = 0;
            while(true)
            {
                _cursor.set_position(-104 + ((blink++ / 15) % 2), 57 + 12 * sel);
                bn::core::update();
                if(bn::keypad::up_pressed()) sel = 0;
                if(bn::keypad::down_pressed()) sel = 1;
                if(confirm()) break;
                if(bn::keypad::b_pressed()) { sel = 1; break; }
            }
            _cursor.set_visible(false);
            return sel;
        }

    private:
        bn::sprite_text_generator& _gen;
        bn::regular_bg_ptr _panel;
        bn::sprite_ptr _arrow;
        bn::sprite_ptr _cursor;
        text_lines _name;
    };

    // ------------------------------------------------------------ equipo
    // Dibuja la lista del equipo (icono, nombre y vida). La fila 0 lleva un * (va al frente).
    void draw_team_rows(const Game& g, bn::sprite_text_generator& gen, text_lines& t,
                        bn::vector<bn::sprite_ptr, max_team>& icons)
    {
        for(int i = 0; i < g.team_size; ++i)
        {
            const int y = -50 + i * 20;
            bn::sprite_ptr icon = creature_item[g.team[i].id]->create_sprite(-92, y);
            icon.set_scale(0.28);
            icons.push_back(icon);
            bn::string<24> name(i == 0 ? "*" : "");
            name.append(species[g.team[i].id].name);
            say(gen, t, -76, y, name);
            if(g.team[i].hp > 0)
            {
                bn::string<16> hp("HP ");
                hp.append(bn::to_string<8>(g.team[i].hp));
                say(gen, t, 48, y, hp);
            }
            else
            {
                say(gen, t, 48, y, "KO");
            }
        }
    }

    // Elegir un animal vivo del equipo. Devuelve su indice, o -1 si cancelas (solo si !must_pick).
    int pick_member(Game& g, bn::sprite_text_generator& gen, bool must_pick)
    {
        text_lines t;
        bn::vector<bn::sprite_ptr, max_team> icons;
        say(gen, t, -112, -70, "ELEGI UN ANIMAL");
        draw_team_rows(g, gen, t, icons);
        say(gen, t, -112, 70, must_pick ? "A: elegir" : "A: elegir  B: volver");
        bn::sprite_ptr cursor = bn::sprite_items::arrow_right.create_sprite(-112, -50);
        int sel = first_alive(g);
        if(sel < 0) sel = 0;
        int blink = 0;
        while(true)
        {
            cursor.set_position(-112 + ((blink++ / 15) % 2), -50 + 20 * sel);
            bn::core::update();
            if(bn::keypad::up_pressed() && sel > 0) --sel;
            if(bn::keypad::down_pressed() && sel < g.team_size - 1) ++sel;
            if(confirm() && g.team[sel].hp > 0) return sel;
            if(! must_pick && bn::keypad::b_pressed()) return -1;
        }
    }

    // ------------------------------------------------------------ animaciones de combate
    const bn::color flash_color(31, 31, 31);

    void set_flash(bn::sprite_ptr& s, bn::fixed intensity)
    {
        bn::sprite_palette_ptr palette = s.palette();
        palette.set_fade(flash_color, intensity);
    }

    void set_rot(bn::sprite_ptr& s, bn::fixed degrees)
    {
        while(degrees < 0) degrees += 360;
        while(degrees >= 360) degrees -= 360;
        s.set_rotation_angle(degrees);
    }

    int bar_index(int hp, int max_hp)
    {
        if(hp <= 0) return 0;
        int i = (hp * 28 + max_hp - 1) / max_hp;
        return i > 28 ? 28 : i;
    }

    // La barra de vida baja de a poco hasta el nuevo valor
    void drain_bar(bn::sprite_ptr& bar, int& current, int target)
    {
        while(current != target)
        {
            current += target > current ? 1 : -1;
            bar.set_item(bn::sprite_items::hpbar, current);
            bn::core::update();
        }
    }

    // Entrada: los dos animales llegan deslizandose desde los costados
    void anim_enter(bn::sprite_ptr& wild, bn::fixed_point wild_home, bn::sprite_ptr& mine, bn::fixed_point mine_home)
    {
        for(int f = 20; f >= 0; --f)
        {
            bn::fixed off = bn::fixed(f * f) / 4;
            wild.set_x(wild_home.x() + off);
            mine.set_x(mine_home.x() - off);
            bn::core::update();
        }
    }

    // Ataque: el atacante embiste, el rival vibra y se pone blanco, aparece el golpe y el numero de dano
    void anim_attack(bn::sprite_text_generator& gen, bn::sprite_ptr& attacker, bn::fixed_point home_a, int dir,
                     bn::sprite_ptr& target, bn::fixed_point home_t, int dmg)
    {
        bn::sprite_ptr hit = bn::sprite_items::hit.create_sprite(home_t.x(), home_t.y(), 0);
        hit.set_visible(false);
        for(int f = 1; f <= 8; ++f)                         // embestida
        {
            attacker.set_x(home_a.x() + dir * f * 4);
            bn::core::update();
        }

        text_lines number;
        bn::string<8> txt("-");
        txt.append(bn::to_string<4>(dmg));
        gen.set_center_alignment();
        gen.generate(home_t.x(), home_t.y() - 36, txt, number);
        gen.set_left_alignment();

        hit.set_visible(true);
        for(int f = 0; f < 24; ++f)
        {
            if(f < 9) hit.set_item(bn::sprite_items::hit, f / 3);
            else hit.set_visible(false);

            bn::fixed shake = 0;
            if(f < 16) shake = ((f % 4) < 2 ? 1 : -1) * bn::fixed(16 - f) / 4;
            target.set_x(home_t.x() + shake);
            set_flash(target, (f < 12 && (f / 2) % 2 == 0) ? bn::fixed(0.8) : bn::fixed(0));

            if(f >= 4 && f < 12)                              // el atacante vuelve a su lugar
            {
                attacker.set_x(home_a.x() + dir * (32 - (f - 3) * 4));
            }
            for(bn::sprite_ptr& s : number)
            {
                s.set_y(s.y() - bn::fixed(0.6));
            }
            bn::core::update();
        }
        attacker.set_x(home_a.x());
        target.set_x(home_t.x());
        set_flash(target, 0);
    }

    // Derrota: se aplasta, se pone blanco y desaparece
    void anim_faint(bn::sprite_ptr& s, bn::fixed_point home)
    {
        for(int f = 1; f <= 20; ++f)
        {
            bn::fixed k = bn::fixed(f) / 22;
            s.set_vertical_scale(1 - k);
            s.set_y(home.y() + k * 28);
            set_flash(s, bn::fixed(f) / 20);
            bn::core::update();
        }
        s.set_visible(false);
    }

    // Captura: las boleadoras vuelan en arco, atrapan al animal, se sacuden y despues
    // lo retienen (chispas) o se rompen y el animal sale.
    void anim_capture(bn::sprite_ptr& wild, bn::fixed_point wild_home, bn::fixed_point from, int shakes, bool success)
    {
        const bn::fixed_point land(wild_home.x(), wild_home.y() + 14);
        bn::sprite_ptr bolas = bn::sprite_items::bolas.create_sprite(from.x(), from.y());
        bolas.set_scale(1.5);

        for(int f = 1; f <= 28; ++f)                          // lanzamiento en arco
        {
            bn::fixed t = bn::fixed(f) / 28;
            bn::fixed arc = 4 * 42 * t * (1 - t);
            bolas.set_position(from.x() + (land.x() - from.x()) * t, from.y() + (land.y() - from.y()) * t - arc);
            set_rot(bolas, bn::fixed(f * 36));
            bn::core::update();
        }

        for(int f = 1; f <= 16; ++f)                          // el animal queda envuelto y se achica
        {
            bn::fixed s = 1 - bn::fixed(f) * bn::fixed(0.053);
            wild.set_scale(s);
            wild.set_y(wild_home.y() + (1 - s) * 26);
            set_flash(wild, bn::fixed(f) / 16);
            set_rot(bolas, bn::fixed(f * 22));
            bn::core::update();
        }
        wild.set_visible(false);
        set_rot(bolas, 0);

        for(int k = 0; k < shakes; ++k)                       // sacudidas
        {
            for(int f = 0; f < 24; ++f)
            {
                set_rot(bolas, bn::degrees_lut_sin(bn::fixed(f * 15)) * 28);
                bn::core::update();
            }
            set_rot(bolas, 0);
            for(int f = 0; f < 16; ++f)
            {
                bn::core::update();
            }
        }

        if(success)                                           // chispas: queda capturado
        {
            const bn::fixed speed = bn::fixed(2.2);
            bn::vector<bn::sprite_ptr, 8> sparks;
            bn::fixed_point vel[8];
            for(int i = 0; i < 8; ++i)
            {
                bn::fixed a = i * 45;
                sparks.push_back(bn::sprite_items::spark.create_sprite(land.x(), land.y() - 8, i % 2));
                vel[i] = bn::fixed_point(bn::degrees_lut_cos(a) * speed, bn::degrees_lut_sin(a) * speed - 1);
            }
            for(int f = 0; f < 32; ++f)
            {
                for(int i = 0; i < 8; ++i)
                {
                    sparks[i].set_position(sparks[i].position() + vel[i]);
                    vel[i] = bn::fixed_point(vel[i].x(), vel[i].y() + bn::fixed(0.1));
                    sparks[i].set_scale(1 + bn::fixed(f) / 16);
                    sparks[i].set_visible(f < 24 || (f % 2) == 0);
                }
                if(f == 10) bolas.set_visible(false);
                bn::core::update();
            }
        }
        else                                                  // se rompe la red y el animal escapa
        {
            wild.set_visible(true);
            for(int f = 1; f <= 14; ++f)
            {
                bn::fixed s = bn::fixed(0.15) + bn::fixed(0.85) * f / 14;
                wild.set_scale(s);
                wild.set_y(wild_home.y() + (1 - s) * 26);
                set_flash(wild, 1 - bn::fixed(f) / 14);
                bolas.set_y(bolas.y() - 5);
                set_rot(bolas, bn::fixed(f * 50));
                bn::core::update();
            }
            wild.set_scale(1);
            wild.set_y(wild_home.y());
            set_flash(wild, 0);
        }
    }

    // ------------------------------------------------------------ combate
    enum class Result { WON, CAPTURED, FLED, FAINTED };

    // trainer = true: duelo contra el animal de otra persona (no se captura ni se huye).
    Result battle(Game& g, bn::sprite_text_generator& gen, int id, int zone, bool trainer = false, int hp_override = -1)
    {
        const Species& sp = species[id];
        const int wild_max = hp_override > 0 ? hp_override : sp.hp;
        int wild_hp = wild_max;
        int active = first_alive(g);

        const bn::fixed_point wild_home(56, -34);
        const bn::fixed_point mine_home(-56, -2);

        bn::regular_bg_ptr scene = battle_bg_item[zone]->create_bg(0, 0);
        bn::optional<bn::sprite_ptr> wild, mine, cursor, wbar, mbar;
        int wbar_idx = 0;
        int mbar_idx = 0;

        // Tu animal (y su barra de vida)
        auto place_mine = [&]()
        {
            mine = creature_item[g.team[active].id]->create_sprite(mine_home.x(), mine_home.y());
            mbar_idx = bar_index(g.team[active].hp, species[g.team[active].id].hp);
            mbar = bn::sprite_items::hpbar.create_sprite(66, 17, mbar_idx);
        };

        // Todo el escenario: el rival mira hacia tu animal (espejado), ambos apoyados en sus plataformas
        auto place_all = [&]()
        {
            wild = creature_item[id]->create_sprite(wild_home.x(), wild_home.y());
            wild->set_horizontal_flip(true);
            wbar_idx = bar_index(wild_hp, wild_max);
            wbar = bn::sprite_items::hpbar.create_sprite(-58, -59, wbar_idx);
            cursor = bn::sprite_items::arrow_right.create_sprite(-104, 49);
            place_mine();
        };
        place_all();

        Result result = Result::FLED;
        int sel = 0;    // 0 Atacar, 1 Capturar / 2 Cambiar, 3 Huir (cuadricula de 2x2)

        anim_enter(*wild, wild_home, *mine, mine_home);
        {
            bn::string<48> s(trainer ? "Te desafian con " : "Aparecio un ");
            s.append(sp.name);
            s.append("!");
            message(gen, s);
        }

        // Pantalla de seleccion de equipo: oculta el escenario para que entre todo el texto
        auto choose_member = [&](bool must) -> int
        {
            scene.set_visible(false);
            wild.reset();
            mine.reset();
            cursor.reset();
            wbar.reset();
            mbar.reset();
            int pick = pick_member(g, gen, must);
            scene.set_visible(true);
            if(pick >= 0)
            {
                active = pick;
            }
            place_all();
            return pick;
        };

        while(true)
        {
            // Menu con flechita: flechas mueven, A o Enter eligen
            int choice = -1;
            {
                text_lines t;
                say(gen, t, -112, -68, sp.name);
                bn::string<32> b(species[g.team[active].id].name);
                b.append(" ");
                b.append(bn::to_string<8>(g.team[active].hp));
                b.append("/");
                b.append(bn::to_string<8>(species[g.team[active].id].hp));
                say(gen, t, 20, 8, b);
                say(gen, t, -92, 49, "Atacar");
                say(gen, t, -8, 49, "Capturar");
                say(gen, t, -92, 65, "Cambiar");
                say(gen, t, -8, 65, "Huir");
                int blink = 0;
                while(choice < 0)
                {
                    const int col = sel % 2;
                    const int row = sel / 2;
                    cursor->set_position((col == 0 ? -104 : -20) + ((blink++ / 15) % 2), row == 0 ? 49 : 65);
                    bn::core::update();
                    if(bn::keypad::left_pressed() && col == 1) --sel;
                    if(bn::keypad::right_pressed() && col == 0) ++sel;
                    if(bn::keypad::up_pressed() && row == 1) sel -= 2;
                    if(bn::keypad::down_pressed() && row == 0) sel += 2;
                    if(confirm()) choice = sel;
                }
            }

            const Species& mine_sp = species[g.team[active].id];

            if(choice == 0)             // Atacar
            {
                int dmg = 4 + g.rng.get_int(mine_sp.atk + 1);
                wild_hp -= dmg;
                if(wild_hp < 0) wild_hp = 0;
                bn::string<48> s(mine_sp.name);
                s.append(" ataca: -");
                s.append(bn::to_string<8>(dmg));
                anim_attack(gen, *mine, mine_home, 1, *wild, wild_home, dmg);
                drain_bar(*wbar, wbar_idx, bar_index(wild_hp, wild_max));
                if(wild_hp <= 0)
                {
                    anim_faint(*wild, wild_home);
                    message(gen, s, "Ganaste el combate!");
                    result = Result::WON;
                    break;
                }
                message(gen, s);
            }
            else if(choice == 1)        // Capturar
            {
                if(trainer)
                {
                    message(gen, "No podes capturar el animal", "de otra persona!");
                    continue;
                }
                int chance = 15 + 75 * (wild_max - wild_hp) / wild_max;
                const bool ok = g.rng.get_int(100) < chance;
                anim_capture(*wild, wild_home, bn::fixed_point(mine_home.x() + 30, mine_home.y() - 8),
                             ok ? 3 : 1 + g.rng.get_int(2), ok);
                if(ok)
                {
                    g.captured[id] = true;
                    bn::string<48> s("Capturaste a ");
                    s.append(sp.name);
                    s.append("!");
                    if(g.team_size < max_team)
                    {
                        g.team[g.team_size].id = id;
                        g.team[g.team_size].hp = wild_hp;
                        ++g.team_size;
                        bn::string<48> j(sp.name);
                        j.append(" se une a tu equipo.");
                        message(gen, s, j);
                    }
                    else
                    {
                        message(gen, s, "Equipo lleno: va al corral.");
                    }
                    result = Result::CAPTURED;
                    break;
                }
                message(gen, "Se escapo de la red!");
            }
            else if(choice == 2)        // Cambiar de animal
            {
                const int previous = active;
                int pick = choose_member(false);
                if(pick < 0 || pick == previous)
                {
                    continue;
                }
                bn::string<48> s("Adelante, ");
                s.append(species[g.team[active].id].name);
                s.append("!");
                message(gen, s);
            }
            else                        // Huir
            {
                if(trainer)
                {
                    message(gen, "No podes huir de un duelo!");
                    continue;
                }
                if(g.rng.get_int(100) < 65)
                {
                    message(gen, "Escapaste sin problemas.");
                    result = Result::FLED;
                    break;
                }
                message(gen, "No pudiste escapar!");
            }

            // Turno del rival
            int dmg = 2 + g.rng.get_int(sp.atk);
            g.team[active].hp -= dmg;
            if(g.team[active].hp < 0) g.team[active].hp = 0;
            bn::string<48> s(sp.name);
            s.append(" ataca: -");
            s.append(bn::to_string<8>(dmg));
            anim_attack(gen, *wild, wild_home, -1, *mine, mine_home, dmg);
            drain_bar(*mbar, mbar_idx, bar_index(g.team[active].hp, species[g.team[active].id].hp));
            if(g.team[active].hp <= 0)
            {
                anim_faint(*mine, mine_home);
                bn::string<48> f(species[g.team[active].id].name);
                f.append(" no puede mas...");
                message(gen, s, f);
                if(first_alive(g) < 0)
                {
                    result = Result::FAINTED;
                    break;
                }
                // Hay que mandar a otro
                choose_member(true);
                bn::string<48> n("Adelante, ");
                n.append(species[g.team[active].id].name);
                n.append("!");
                message(gen, n);
            }
            else
            {
                message(gen, s);
            }
        }

        return result;
    }

    // ------------------------------------------------------------ menu: equipo y fauna
    void pause_menu(Game& g, bn::sprite_text_generator& gen)
    {
        int page = 0;      // 0 = equipo, 1 = fauna capturada
        int sel = 0;
        bool open = true;
        while(open)
        {
            text_lines t;
            bn::vector<bn::sprite_ptr, 10> icons;
            bn::vector<bn::sprite_ptr, max_team> team_icons;
            bn::sprite_ptr cursor = bn::sprite_items::arrow_right.create_sprite(-112, -50);
            cursor.set_visible(page == 0);

            if(page == 0)
            {
                say(gen, t, -112, -70, "EQUIPO");
                say(gen, t, 40, -70, "< > fauna");
                draw_team_rows(g, gen, t, team_icons);
                say(gen, t, -112, 70, "A: al frente  B: volver");
            }
            else
            {
                int count = 0;
                for(bool c : g.captured) count += c;
                bn::string<32> head("FAUNA ");
                head.append(bn::to_string<8>(count));
                head.append("/10");
                say(gen, t, -112, -70, head);
                say(gen, t, 40, -70, "< > equipo");
                for(int i = 0; i < species_count; ++i)
                {
                    int col_x = -108 + (i / 5) * 116;
                    int row_y = -44 + (i % 5) * 24;
                    if(g.captured[i])
                    {
                        bn::sprite_ptr icon = creature_item[i]->create_sprite(col_x + 8, row_y);
                        icon.set_scale(0.36);
                        icons.push_back(icon);
                        say(gen, t, col_x + 22, row_y, species[i].name);
                    }
                    else
                    {
                        say(gen, t, col_x + 22, row_y, "???");
                    }
                }
                say(gen, t, -112, 70, "B: volver");
            }

            bool changed = false;
            int blink = 0;
            while(open && ! changed)
            {
                cursor.set_position(-112 + ((blink++ / 15) % 2), -50 + 20 * sel);
                bn::core::update();
                if(bn::keypad::b_pressed())
                {
                    open = false;
                }
                else if(bn::keypad::left_pressed() || bn::keypad::right_pressed() ||
                        bn::keypad::l_pressed() || bn::keypad::r_pressed())
                {
                    page = 1 - page;
                    changed = true;
                }
                else if(page == 0)
                {
                    if(bn::keypad::up_pressed() && sel > 0) --sel;
                    if(bn::keypad::down_pressed() && sel < g.team_size - 1) ++sel;
                    if(confirm() && sel > 0)
                    {
                        Member tmp = g.team[0];
                        g.team[0] = g.team[sel];
                        g.team[sel] = tmp;
                        sel = 0;
                        changed = true;
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ ayuda
    constexpr int help_pages = 4;
    constexpr int help_max_lines = 6;
    const char* const help_text[help_pages][help_max_lines] = {
        {"Flechas: moverse", "B (mantener): correr", "A: hablar / aceptar", "START: equipo y fauna", "SELECT: mapa", "L: esta ayuda"},
        {"Combate (flechas + A):", "Atacar    Capturar", "Cambiar   Huir", "Capturar: mejor con", "poca vida del rival", nullptr},
        {"Entra a las casas por la", "puerta. La Veterinaria", "(techo azul) cura a todo", "tu equipo. Maximo 6.", "El resto va al corral.", nullptr},
        {"TECLADO en mGBA:", "A=X  B=Z  L=A  R=S", "START=Enter", "SELECT=M", "Flechas=flechas", nullptr},
    };

    void help_screen(bn::sprite_text_generator& gen)
    {
        int page = 0;
        bool open = true;
        while(open)
        {
            text_lines t;
            bn::string<32> title("AYUDA ");
            title.append(bn::to_string<8>(page + 1));
            title.append("/");
            title.append(bn::to_string<8>(help_pages));
            say(gen, t, -112, -70, title);
            say(gen, t, 20, -70, "< > pagina");
            for(int i = 0; i < help_max_lines; ++i)
            {
                if(help_text[page][i])
                {
                    say(gen, t, -112, -48 + i * 12, help_text[page][i]);
                }
            }
            say(gen, t, -112, 68, "L o B: cerrar");

            bool changed = false;
            while(open && ! changed)
            {
                bn::core::update();
                if(bn::keypad::l_pressed() || bn::keypad::b_pressed())
                {
                    open = false;
                }
                else if((bn::keypad::right_pressed() || bn::keypad::a_pressed()) && page < help_pages - 1)
                {
                    ++page;
                    changed = true;
                }
                else if(bn::keypad::left_pressed() && page > 0)
                {
                    --page;
                    changed = true;
                }
            }
        }
    }

    // Direccion segun las flechas apretadas: 0 abajo, 1 arriba, 2 izquierda, 3 derecha, -1 ninguna
    int held_direction()
    {
        if(bn::keypad::left_held())  return 2;
        if(bn::keypad::right_held()) return 3;
        if(bn::keypad::up_held())    return 1;
        if(bn::keypad::down_held())  return 0;
        return -1;
    }

    constexpr int dir_dx[4] = {0, 0, -1, 1};
    constexpr int dir_dy[4] = {1, -1, 0, 0};
}

int main()
{
    bn::core::init();
    bn::bg_palettes::set_transparent_color(backdrop_world);

    Game g;
    bn::sprite_text_generator gen(common::variable_8x8_sprite_font);
    gen.set_left_alignment();
    gen.set_bg_priority(0);          // el texto siempre queda por encima de los fondos

    bn::fixed_point pos = tile_center(g.tx, g.ty);
    bn::camera_ptr camera = bn::camera_ptr::create(pos);
    bn::regular_bg_ptr bg = bn::regular_bg_items::world.create_bg(0, 0);
    bg.set_camera(camera);
    bn::sprite_ptr player = bn::sprite_items::player.create_sprite(pos.x(), pos.y() + char_dy, 0);
    player.set_camera(camera);

    // NPCs (quietos, mirando para su lado)
    bn::vector<bn::sprite_ptr, world::npc_count> npc_sprites;
    for(int i = 0; i < world::npc_count; ++i)
    {
        bn::fixed_point p = tile_center(world::npc_tx[i], world::npc_ty[i]);
        bn::sprite_ptr s = npcs[i].item->create_sprite(p.x(), p.y() + char_dy, world::npc_dir[i]);
        s.set_camera(camera);
        npc_sprites.push_back(s);
    }

    // Perrito: ocupa el casillero donde estaba el jugador un paso antes
    bn::fixed_point dog_pos = tile_center(g.dog_tx, g.dog_ty);
    bn::sprite_ptr dog = bn::sprite_items::dog.create_sprite(dog_pos.x(), dog_pos.y(), 3 * 4);
    dog.set_camera(camera);
    int dog_dir = 3;
    int dog_from_x = g.dog_tx, dog_from_y = g.dog_ty;

    int dir = 0;           // 0 abajo, 1 arriba, 2 izquierda, 3 derecha
    bool moving = false;
    int move_t = 0;
    int step_len = 16;     // cuadros por casillero: 16 caminando, 8 corriendo (mantener B)
    int step_px = 1;
    int turn_delay = 0;    // girar sin avanzar: un toque corto solo cambia de direccion
    int dx = 0, dy = 0;
    Zone zone = zone_at(g.tx, g.ty);
    int province = province_at(g.tx, g.ty);
    int banner_timer = 150;
    text_lines banner;
    gen.generate(-112, -74, argmap::names[province], banner);
    gen.generate(-112, -62, zone_names[zone], banner);

    bn::music_items::chacarera.play(music_volume_world);

    // Pista de controles al empezar
    int hint_timer = 360;
    text_lines hint;
    gen.generate(-112, 72, "A:ayuda M:mapa Enter:equipo", hint);

    // Mapa general (SELECT / M)
    bool map_open = false;
    int map_blink = 0;
    bn::optional<bn::regular_bg_ptr> map_bg;
    bn::optional<bn::sprite_ptr> mm_marker;
    text_lines mm_text;

    // Oculta/muestra el mundo y los carteles para las pantallas de texto, interiores o mapa
    auto set_world_visible = [&](bool visible)
    {
        bg.set_visible(visible);
        player.set_visible(visible);
        dog.set_visible(visible);
        for(bn::sprite_ptr& s : npc_sprites)
        {
            s.set_visible(visible);
        }
        bn::bg_palettes::set_transparent_color(visible ? backdrop_world : backdrop_dark);
    };

    auto clear_banners = [&]()
    {
        banner.clear();
        hint.clear();
        banner_timer = 0;
        hint_timer = 0;
    };

    auto show_zone_banner = [&]()
    {
        banner.clear();
        gen.generate(-112, -74, argmap::names[province], banner);
        gen.generate(-112, -62, zone_names[zone], banner);
        banner_timer = 150;
    };

    // Lanza un combate ocultando el mundo; si todo tu equipo cae, vuelves al inicio curado.
    auto start_battle = [&](int id, bool trainer, int hp_override) -> Result
    {
        clear_banners();
        set_world_visible(false);
        bn::music_items::malambo.play(music_volume_battle);
        Result r = battle(g, gen, id, int(zone), trainer, hp_override);
        bn::music_items::chacarera.play(music_volume_world);
        set_world_visible(true);
        if(r == Result::FAINTED)
        {
            heal_all(g);
            g.tx = start_tx;
            g.ty = start_ty;
            g.dog_tx = start_tx - 1;
            g.dog_ty = start_ty;
            pos = tile_center(g.tx, g.ty);
            dog_pos = tile_center(g.dog_tx, g.dog_ty);
            zone = zone_at(g.tx, g.ty);
            province = province_at(g.tx, g.ty);
            show_zone_banner();
        }
        return r;
    };

    // Conversacion con un NPC del mapa
    auto talk_to = [&](int i)
    {
        clear_banners();
        // El NPC te mira de frente
        static const int opposite[4] = {1, 0, 3, 2};
        npc_sprites[i].set_item(*npcs[i].item, opposite[dir]);

        DialogBox box(gen, npcs[i].name);
        switch(i)
        {
        case 0:     // Don Segundo
            box.page("Ey, pibe! Bienvenido a la pampa.", "Aca el pasto alto esta lleno");
            box.page("de bichos. Mate te cuida las", "espaldas. Capturalos todos!");
            box.page("En las casas con techo azul", "curan a tus animales.");
            break;
        case 1:     // Lila
            box.page("Soy Lila, guardaparque. Cuido", "la fauna de esta zona.");
            box.page("Se ve cansado tu equipo...", "Descansen un ratito.");
            heal_all(g);
            box.page("Tus animales recuperaron", "toda su energia!");
            break;
        case 2:     // Beto
            box.page("Yo pesco en la caleta. Si vas", "a la costa vas a ver pinguinos.");
            box.page("Son tiernos, pero pican si", "los apuras!");
            box.page("Condores? Solo en los Andes,", "alla donde falta el aire.");
            break;
        case 3:     // Tomas, duelo
            if(g.duel_won)
            {
                box.page("Ya me ganaste, pibe. Buen ojo", "para la pelea. Segui asi!");
                break;
            }
            box.page("Eh, vos! Me dijeron que tenes", "un equipo guapo.");
            box.page("Yo tengo un zorrito pampeano", "que nunca pierde.");
            if(box.choose("Aceptas un duelo?", "Si, vamos!", "Ahora no") == 0)
            {
                box.page("Dale! Que gane el mejor!");
                Result r = start_battle(5, true, 44);
                if(r == Result::WON)
                {
                    g.duel_won = true;
                    box.page("Bien peleado, pibe! Te debo", "un mate. Hasta la proxima!");
                }
            }
            else
            {
                box.page("Cuando quieras, aca estoy.");
            }
            break;
        case 4:     // Profe Ana
        {
            int count = 0;
            for(bool c : g.captured) count += c;
            bn::string<40> l1("Capturaste ");
            l1.append(bn::to_string<8>(count));
            l1.append(" de 10 animales.");
            box.page("Soy la Profe Ana. Estudio la", "fauna autoctona argentina.");
            box.page(l1.c_str(), count == species_count ? "Sos un verdadero guardian!" : "Mira START para ver tu lista.");
            break;
        }
        default:    // Wara
            box.page("Los Andes: aire finito y vistas", "de cine. Cuidado con los condores!");
            heal_all(g);
            box.page("Tomen, mate caliente para", "todo el equipo. Curados!");
            break;
        }
        // devolver al NPC a su posicion original
        npc_sprites[i].set_item(*npcs[i].item, world::npc_dir[i]);
    };

    // Conversacion con el habitante de una casa o la veterinaria
    auto talk_inside = [&](bool vet, int rid)
    {
        const Npc& who = vet ? vet_npc : residents[rid];
        DialogBox box(gen, who.name);
        if(vet)
        {
            box.page("Bienvenido a la Veterinaria!", "Cuidamos a toda la fauna.");
            if(box.choose("Curamos a tus animales?", "Si, por favor", "No, gracias") == 0)
            {
                box.page("Un momentito...", "Ya los reviso a todos.");
                heal_all(g);
                box.page("Listo! Tus animales estan", "como nuevos. Vuelvan pronto!");
            }
            else
            {
                box.page("Cuando quieras. Aca estamos.");
            }
        }
        else if(rid == 0)
        {
            box.page("Pasa, pasa, mijo! Te sirvo unos", "mates con tortas fritas?");
            box.page("Cuida a tus animalitos, que el", "campo es grande y bravo.");
        }
        else if(rid == 1)
        {
            box.page("Mira! Vi un carpincho gigante", "en el rio. Parecia un sillon!");
            box.page("Cuando sea grande voy a ser", "guardaparque como Lila.");
        }
        else
        {
            box.page("Antes por aca pasaban tropas", "de ganado. Ahora, puros bichos.");
            box.page("El yaguarete? Dicen que baja", "al rio cuando hace calor.");
        }
    };

    // Entrar a un edificio: cuarto de 15x10 casilleros, se sale por el felpudo de abajo
    auto enter_building = [&](bool vet, int door_x, int door_y)
    {
        clear_banners();
        set_world_visible(false);
        const int rid = (door_x * 7 + door_y * 3) % resident_count;
        const unsigned char* grid = vet ? interior::vet_grid : interior::house_grid;
        const int nx = vet ? interior::vet_npc_x : interior::house_npc_x;
        const int ny = vet ? interior::vet_npc_y : interior::house_npc_y;
        const Npc& who = vet ? vet_npc : residents[rid];

        bn::regular_bg_ptr room = (vet ? bn::regular_bg_items::interior_vet : bn::regular_bg_items::interior_house).create_bg(0, 0);
        auto center = [](int x, int y) { return bn::fixed_point(-120 + 16 * x + 8, -80 + 16 * y + 8); };

        bn::fixed_point np = center(nx, ny);
        bn::sprite_ptr who_sprite = who.item->create_sprite(np.x(), np.y() + char_dy, 0);

        camera.set_position(0, 0);       // el jugador usa la camara: asi sus coordenadas son las de pantalla
        player.set_visible(true);
        int ix = interior::spawn_x, iy = interior::spawn_y;
        int idir = 1;
        bool imoving = false;
        int it = 0;
        int idx = 0, idy = 0;
        bn::fixed_point ipos = center(ix, iy);
        player.set_item(bn::sprite_items::player, idir * 4);
        player.set_position(ipos.x(), ipos.y() + char_dy);

        while(true)
        {
            if(! imoving)
            {
                int want = held_direction();
                if(want >= 0)
                {
                    if(want != idir)
                    {
                        idir = want;
                        player.set_item(bn::sprite_items::player, idir * 4);
                    }
                    else
                    {
                        idx = dir_dx[idir];
                        idy = dir_dy[idir];
                        int tx2 = ix + idx, ty2 = iy + idy;
                        if(tx2 >= 0 && ty2 >= 0 && tx2 < interior::width && ty2 < interior::height &&
                           ! (tx2 == nx && ty2 == ny))
                        {
                            unsigned char cell = grid[ty2 * interior::width + tx2];
                            if(cell == 0 || cell == 3)
                            {
                                imoving = true;
                                it = 0;
                            }
                        }
                    }
                }
                else if(bn::keypad::a_pressed())
                {
                    int fx = ix + dir_dx[idir], fy = iy + dir_dy[idir];
                    bool can_talk = (fx == nx && fy == ny);
                    if(! can_talk && fx >= 0 && fy >= 0 && fx < interior::width && fy < interior::height &&
                       grid[fy * interior::width + fx] == 2)
                    {
                        can_talk = (fx + dir_dx[idir] == nx && fy + dir_dy[idir] == ny);   // a traves del mostrador
                    }
                    if(can_talk)
                    {
                        talk_inside(vet, rid);
                    }
                }
            }

            if(imoving)
            {
                ++it;
                ipos = center(ix, iy) + bn::fixed_point(idx * 2 * it, idy * 2 * it);
                player.set_item(bn::sprite_items::player, idir * 4 + (it * 4 / 8 > 3 ? 3 : it * 4 / 8));
                if(it == 8)
                {
                    ix += idx;
                    iy += idy;
                    imoving = false;
                    ipos = center(ix, iy);
                    player.set_item(bn::sprite_items::player, idir * 4);
                    if(grid[iy * interior::width + ix] == 3)
                    {
                        break;      // salio por el felpudo
                    }
                }
            }

            player.set_position(ipos.x(), ipos.y() + char_dy);
            bn::core::update();
        }

        // Volver a la calle: frente a la puerta, mirando hacia abajo
        g.tx = door_x;
        g.ty = door_y + 1;
        g.dog_tx = door_x;
        g.dog_ty = door_y;
        dir = 0;
        pos = tile_center(g.tx, g.ty);
        dog_pos = tile_center(g.dog_tx, g.dog_ty);
        dog_from_x = g.dog_tx;
        dog_from_y = g.dog_ty;
        dog_dir = 0;
        player.set_item(bn::sprite_items::player, 0);
        dog.set_item(bn::sprite_items::dog, 0);
        player.set_position(pos.x(), pos.y() + char_dy);
        dog.set_position(dog_pos);
        camera.set_position(pos);
        set_world_visible(true);
    };

    while(true)
    {
        // ---- mapa abierto: solo se atiende SELECT / B
        if(map_open)
        {
            {
                const int idx = g.ty * world::width + g.tx;
                mm_marker->set_position(argmap::screen_x0 + argmap::marker_x[idx],
                                        argmap::screen_y0 + argmap::marker_y[idx]);
            }
            mm_marker->set_visible((++map_blink / 15) % 2 == 0);
            if(bn::keypad::select_pressed() || bn::keypad::b_pressed())
            {
                map_open = false;
                map_bg.reset();
                mm_marker.reset();
                mm_text.clear();
                set_world_visible(true);
            }
            bn::core::update();
            continue;
        }

        if(! moving && bn::keypad::select_pressed())
        {
            map_open = true;
            map_blink = 0;
            clear_banners();
            set_world_visible(false);
            map_bg = bn::regular_bg_items::mapscreen.create_bg(0, 0);
            mm_marker = bn::sprite_items::marker.create_sprite(0, 0);
            gen.generate(-14, -22, "Provincia:", mm_text);
            gen.generate(-14, -10, argmap::names[province], mm_text);
            gen.generate(-14, 8, "Zona:", mm_text);
            gen.generate(-14, 20, zone_names[zone], mm_text);
            gen.generate(-14, 72, "M: cerrar", mm_text);
            bn::core::update();
            continue;
        }

        if(! moving && bn::keypad::l_pressed())
        {
            clear_banners();
            set_world_visible(false);
            help_screen(gen);
            set_world_visible(true);
            bn::core::update();
            continue;
        }

        if(hint_timer > 0 && --hint_timer == 0)
        {
            hint.clear();
        }

        if(! moving)
        {
            const int want = held_direction();
            if(want >= 0)
            {
                if(want != dir)
                {
                    // un toque corto solo gira; si seguis apretando, empieza a caminar
                    dir = want;
                    turn_delay = 5;
                    player.set_item(bn::sprite_items::player, dir * 4);
                }
                else if(turn_delay > 0)
                {
                    --turn_delay;
                }
                else
                {
                    dx = dir_dx[dir];
                    dy = dir_dy[dir];
                    if(walkable(g.tx + dx, g.ty + dy))
                    {
                        moving = true;
                        move_t = 0;
                        step_len = bn::keypad::b_held() ? 8 : 16;
                        step_px = 16 / step_len;
                        // el perrito va hacia el casillero que dejas libre
                        dog_from_x = g.dog_tx;
                        dog_from_y = g.dog_ty;
                        int ddx = g.tx - g.dog_tx;
                        int ddy = g.ty - g.dog_ty;
                        if(ddy > 0) dog_dir = 0; else if(ddy < 0) dog_dir = 1;
                        else if(ddx < 0) dog_dir = 2; else if(ddx > 0) dog_dir = 3;
                    }
                }
            }
            else if(bn::keypad::a_pressed())
            {
                // hablar con quien tengas enfrente
                int n = npc_at(g.tx + dir_dx[dir], g.ty + dir_dy[dir]);
                if(n >= 0)
                {
                    talk_to(n);
                }
            }
            else if(bn::keypad::start_pressed())
            {
                clear_banners();
                set_world_visible(false);
                pause_menu(g, gen);
                set_world_visible(true);
            }
        }

        if(moving)
        {
            ++move_t;
            pos = tile_center(g.tx, g.ty) + bn::fixed_point(dx * step_px * move_t, dy * step_px * move_t);
            // ciclo de caminata: quieto, pie izquierdo, quieto, pie derecho
            int phase = move_t * 4 / step_len;
            if(phase > 3) phase = 3;
            player.set_item(bn::sprite_items::player, dir * 4 + phase);

            // Perrito: avanza hacia donde estaba el jugador (mismo ritmo)
            bn::fixed_point from = tile_center(dog_from_x, dog_from_y);
            bn::fixed_point to = tile_center(g.tx, g.ty);
            dog_pos = from + (to - from) * move_t / step_len;
            dog.set_item(bn::sprite_items::dog, dog_dir * 4 + phase);

            if(move_t == step_len)
            {
                g.dog_tx = g.tx;
                g.dog_ty = g.ty;
                g.tx += dx;
                g.ty += dy;
                moving = false;
                pos = tile_center(g.tx, g.ty);
                player.set_item(bn::sprite_items::player, dir * 4);
                dog.set_item(bn::sprite_items::dog, dog_dir * 4);

                const Tile here = tile_at(g.tx, g.ty);

                // Cambio de zona o de provincia -> cartel
                Zone z = zone_at(g.tx, g.ty);
                int p = province_at(g.tx, g.ty);
                if(z != zone || p != province)
                {
                    zone = z;
                    province = p;
                    show_zone_banner();
                }

                if(here == T_PUERTA || here == T_VETPUERTA)
                {
                    // entras al edificio por la puerta
                    enter_building(here == T_VETPUERTA, g.tx, g.ty);
                }
                else if(tall_grass(here) && g.rng.get_int(100) < 14)
                {
                    // Encuentro en pasto alto
                    int id = encounter_table[zone][g.rng.get_int(max_table)];
                    start_battle(id, false, -1);
                }
            }
        }

        if(banner_timer > 0 && --banner_timer == 0)
        {
            banner.clear();
        }

        player.set_position(pos.x(), pos.y() + char_dy);
        dog.set_position(dog_pos);
        camera.set_position(pos);
        bn::core::update();
    }
}
