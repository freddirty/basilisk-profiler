# SPDX-License-Identifier: GPL-2.0-or-later
"""Hungarian interface texts. Keys are the English source strings, as written in the code.

tests/test_i18n.py checks that every marked string has an entry here, that no entry is
stale, and that the {fields} match.
"""

CATALOG = {
    # --- tray --------------------------------------------------------------------
    'white': 'fehér',
    'red': 'piros',
    'green': 'zöld',
    'blue': 'kék',
    'cyan': 'cián',
    '{color} slot': '{color} hely',
    'Profile: {name}': 'Profil: {name}',
    'Profile: manual, {slot}': 'Profil: kézi, {slot}',
    'Profile: {name} (manual, {slot})': 'Profil: {name} (kézi, {slot})',
    'M': 'K',
    ' (stage {stage}/{count})': ' ({stage}/{count}. fokozat)',
    'Battery: {percent}%': 'Akku: {percent}%',
    ' (config error)': ' (konfighiba)',
    'Pause': 'Szüneteltetés',
    'Settings…': 'Beállítások…',
    'Config as text': 'Konfig szövegként',
    'Quit': 'Kilépés',
    'Show DPI changes': 'DPI-váltás jelzése',
    'Dock: battery level effect': 'Dokk: akkuszint-effekt',
    'Start with Windows': 'Indítás a Windows-szal',
    'Start at login': 'Indítás bejelentkezéskor',
    'Language': 'Nyelv / Language',
    'Automatic (system)': 'Automatikus (rendszer)',

    # --- short action labels on the mouse drawing ------------------------------------
    'default': 'alapértelmezett',
    'scroll up': 'görgetés fel',
    'mouse button {n}': 'egérgomb {n}',
    'play/pause': 'lejátszás/szünet',
    'next track': 'következő szám',
    'previous track': 'előző szám',
    'stop': 'leállítás',
    'volume up': 'hangerő fel',
    'volume down': 'hangerő le',
    'mute': 'némítás',
    'multimedia': 'multimédia',
    'DPI stage up': 'DPI-fokozat fel',
    'cycle DPI stages': 'DPI-fokozatok körbe',
    'clutch {dpi} DPI': 'clutch {dpi} DPI',
    'next profile': 'következő profil',
    'toggle scroll mode': 'görgő mód váltás',
    'disabled': 'letiltva',
    'other function': 'egyéb funkció',

    # --- profile names -------------------------------------------------------------
    'profile': 'profil',
    '{name} copy': '{name} másolat',
    'a profile with this name already exists: {name}': 'már van ilyen nevű profil: {name}',

    # --- mouse drawing -----------------------------------------------------------------
    'Right click': 'Jobb klikk',
    'Left click': 'Bal klikk',
    'Front side button (Mouse 5)': 'Elülső oldalgomb (Mouse 5)',
    'Back side button (Mouse 4)': 'Hátsó oldalgomb (Mouse 4)',
    'Sensitivity clutch': 'Érzékenység-clutch',
    'DPI stage cycle': 'DPI-fokozat váltás',
    'Scroll mode (tactile / free)': 'Görgő mód (racsnis / sima)',
    'Wheel tilt right': 'Görgő döntése jobbra',
    'Wheel tilt left': 'Görgő döntése balra',
    'Wheel click': 'Görgőkattintás',
    'Profile button (bottom)': 'Profilváltó gomb (alul)',

    # --- button editor -----------------------------------------------------------------
    'Back side button (Mouse Button 4)': 'Hátsó oldalgomb (Mouse Button 4)',
    'Front side button (Mouse Button 5)': 'Elülső oldalgomb (Mouse Button 5)',
    'Sensitivity clutch (thumb button)': 'Érzékenység-clutch (hüvelykujj-gomb)',
    'Scroll mode button (tactile / free)': 'Görgő mód gomb (racsnis / sima)',
    'DPI stage button': 'DPI-fokozat váltó gomb',
    'Button': 'Gomb',
    'Default (factory function)': 'Alapértelmezett (gyári funkció)',
    'Mouse button': 'Egérgomb',
    'Key / combination': 'Billentyű / kombináció',
    'Multimedia': 'Multimédia',
    'DPI function': 'DPI-funkció',
    'Next profile': 'Következő profil',
    'Disabled': 'Letiltva',
    'Left button': 'Bal gomb',
    'Right button': 'Jobb gomb',
    'Middle button': 'Középső gomb',
    'Back (4)': 'Vissza (4)',
    'Forward (5)': 'Előre (5)',
    'Scroll up': 'Görgetés fel',
    'Play / pause': 'Lejátszás / szünet',
    'Next track': 'Következő szám',
    'Previous track': 'Előző szám',
    'Stop': 'Leállítás',
    'Volume up': 'Hangerő fel',
    'Volume down': 'Hangerő le',
    'Mute': 'Némítás',
    'Cycle DPI stages': 'DPI-fokozatok körbe',
    'Sensitivity clutch (while held)': 'Érzékenység-clutch (lenyomva tartva)',
    'click here, then press the key': 'kattints ide, majd nyomd le a billentyűt',
    'The program cannot edit this function yet ({action}).':
        'Ezt a funkciót még nem tudja szerkeszteni a program ({action}).',

    # --- DPI -------------------------------------------------------------------------------
    'DPI stages': 'DPI-fokozatok',
    'The profile sets the DPI stages': 'A profil állítsa be a DPI-fokozatokat',
    'Number of stages': 'Fokozatok száma',
    'active': 'aktív',
    'Stage {n}': '{n}. fokozat',

    # --- cursor ------------------------------------------------------------------------
    'Custom cursor': 'Egyedi kurzor',
    "Use a custom cursor in the profile's windows": 'A profil ablakában egyedi kurzor legyen',
    'e.g. yolomouse-pink-huge.cur': 'pl. yolomouse-pink-huge.cur',
    'Browse…': 'Tallózás…',
    'The program comes with no cursor images: choose your own .cur file (for example '
    "YoloMouse's Cursors/Huge/2.cur). A relative name is looked up in the {folder} folder. "
    'The cursor is only shown while a window of the profile is active.':
        'Kurzorképet a program nem tartalmaz: a saját .cur fájlodat válaszd (például a '
        'YoloMouse Cursors/Huge/2.cur fájlját). A relatív név a {folder} mappában '
        'keresendő. A kurzor csak akkor látszik, amikor a profilhoz tartozó ablak aktív.',
    'Cursor file': 'Kurzorfájl',
    'Scale': 'Nagyítás',
    'Preview': 'Előnézet',
    'Cursor (*.cur *.ico);;All files (*)': 'Kurzor (*.cur *.ico);;Minden fájl (*)',

    # --- rules ---------------------------------------------------------------------------
    'Program': 'Program',
    'Window class (regex)': 'Ablakosztály (regex)',
    'Window title (regex)': 'Ablakcím (regex)',
    'Choose a running window': 'Futó ablak kiválasztása',
    'Window class': 'Ablakosztály',
    'Title': 'Cím',
    'Condition': 'Feltétel',
    'Value': 'Érték',
    'Profile': 'Profil',
    'New rule': 'Új szabály',
    'From a running window…': 'Futó ablakból…',
    'Up': 'Fel',
    'Down': 'Le',
    'The rules are checked from top to bottom; the first match decides. If none matches, '
    'the default profile is used.':
        'A szabályokat felülről lefelé nézi a program; az első egyező dönt. Ha egyik sem '
        'illik, az alapértelmezett profil él.',

    # --- Synapse import ------------------------------------------------------------------
    'Import profiles from Synapse': 'Profilok importálása a Synapse-ból',
    'no button mapping': 'nincs gombkiosztás',
    '  (skipped: {count})': '  (kihagyva: {count})',
    "Profiles found in Synapse's local database. Hypershift mappings and unsupported "
    'buttons are left out.':
        'A Synapse helyi adatbázisában talált profilok. A Hypershift-kiosztások és a nem '
        'támogatott gombok kimaradnak.',
    "Synapse's data folder (copied from Windows: {path})":
        'A Synapse adatmappája (Windowsról átmásolva: {path})',
    'Import': 'Importálás',
    "Cannot read Synapse's data:\n{error}": 'A Synapse adatai nem olvashatók:\n{error}',
    'No Basilisk profile was found.': 'Nem találtam Basilisk-profilt.',

    # --- main window -----------------------------------------------------------------------
    'Profiles': 'Profilok',
    'New': 'Új',
    'Copy': 'Másolat',
    'Rename': 'Átnevezés',
    'Delete': 'Törlés',
    'Make default': 'Legyen az alapértelmezett',
    'Onboard slot in the mouse': 'Beépített hely az egérben',
    'None (switched by the program only)': 'Nincs (csak a program váltja)',
    'Slot 1 (red)': '1. hely (piros)',
    'Slot 2 (green)': '2. hely (zöld)',
    'Slot 3 (blue)': '3. hely (kék)',
    'Slot 4 (cyan)': '4. hely (cián)',
    'A profile written to an onboard slot stays in the mouse: it can be chosen with the '
    'profile button without the program, even on another computer.':
        'A beépített helyre írt profil az egérben marad: a program nélkül, akár másik gépen '
        'is a profilgombbal választható.',
    '   [slot {n}]': '   [{n}. hely]',
    'Buttons': 'Gombok',
    'Cursor': 'Kurzor',
    'Rules (automatic switching)': 'Szabályok (automatikus váltás)',
    'File': 'Fájl',
    'Save': 'Mentés',
    'Import from Synapse…': 'Importálás a Synapse-ból…',
    'Reload from file': 'Újratöltés a fájlból',
    'Reload': 'Újratöltés',
    'New profile': 'Új profil',
    'Profile name:': 'Profil neve:',
    'Delete the profile “{name}” and its rules?':
        'Törlöd a(z) „{name}” profilt és a hozzá tartozó szabályokat?',
    'Cannot save:\n{error}': 'Nem menthető:\n{error}',
    'Saved – the background service picks it up by itself.':
        'Elmentve – a háttérszolgáltatás magától átveszi.',
    'Save the changes?': 'Mented a módosításokat?',

    # --- errors -----------------------------------------------------------------------------
    'Basilisk Profiler – error': 'Basilisk Profiler – hiba',
    'An unexpected error occurred: {error}\n\nThe details are in the log file, and you can '
    'also copy them from here.':
        'Váratlan hiba történt: {error}\n\nA részletek a naplófájlban vannak, és ide kattintva '
        'is kimásolhatók.',
}
