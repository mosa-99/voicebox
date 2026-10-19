//! macOS menu bar in the app's UI language.
//!
//! Tauri's default macOS menu (`Menu::default`) has fixed English labels. This
//! builds the same structure with labels for the language the frontend reports
//! through `set_menu_language`, so the menu bar matches the rest of the UI.
//! Languages without a table here fall back to English. Other platforms keep
//! whatever they had, since Tauri only installs a default menu on macOS.
//!
//! The same command also records the language as the app's AppleLanguages
//! preference (what System Settings' per-app language does), so the items
//! macOS adds itself, open/save panels and permission prompts follow it from
//! the next launch on. Info.plist lists en/de/ar in CFBundleLocalizations so
//! AppKit accepts those.

use tauri::menu::{
    AboutMetadata, Menu, PredefinedMenuItem, Submenu, HELP_SUBMENU_ID, WINDOW_SUBMENU_ID,
};
use tauri::{AppHandle, Runtime};

pub(crate) struct Labels {
    pub(crate) about: &'static str,
    pub(crate) services: &'static str,
    pub(crate) hide: &'static str,
    pub(crate) hide_others: &'static str,
    pub(crate) quit: &'static str,
    pub(crate) file: &'static str,
    pub(crate) close_window: &'static str,
    pub(crate) edit: &'static str,
    pub(crate) undo: &'static str,
    pub(crate) redo: &'static str,
    pub(crate) cut: &'static str,
    pub(crate) copy: &'static str,
    pub(crate) paste: &'static str,
    pub(crate) select_all: &'static str,
    pub(crate) view: &'static str,
    pub(crate) fullscreen: &'static str,
    pub(crate) window: &'static str,
    pub(crate) minimize: &'static str,
    pub(crate) zoom: &'static str,
    pub(crate) help: &'static str,
    /// Menu bar icon: bring the main window back.
    pub(crate) tray_open: &'static str,
}

// Wording follows each language's standard macOS menu titles.
const EN: Labels = Labels {
    about: "About Voicebox",
    services: "Services",
    hide: "Hide Voicebox",
    hide_others: "Hide Others",
    quit: "Quit Voicebox",
    file: "File",
    close_window: "Close Window",
    edit: "Edit",
    undo: "Undo",
    redo: "Redo",
    cut: "Cut",
    copy: "Copy",
    paste: "Paste",
    select_all: "Select All",
    view: "View",
    fullscreen: "Enter Full Screen",
    window: "Window",
    minimize: "Minimize",
    zoom: "Zoom",
    help: "Help",
    tray_open: "Open Voicebox",
};

const DE: Labels = Labels {
    about: "Über Voicebox",
    services: "Dienste",
    hide: "Voicebox ausblenden",
    hide_others: "Andere ausblenden",
    quit: "Voicebox beenden",
    file: "Ablage",
    close_window: "Fenster schließen",
    edit: "Bearbeiten",
    undo: "Widerrufen",
    redo: "Wiederholen",
    cut: "Ausschneiden",
    copy: "Kopieren",
    paste: "Einsetzen",
    select_all: "Alles auswählen",
    view: "Darstellung",
    fullscreen: "Vollbildmodus aktivieren",
    window: "Fenster",
    minimize: "Im Dock ablegen",
    zoom: "Zoomen",
    help: "Hilfe",
    tray_open: "Voicebox öffnen",
};

const AR: Labels = Labels {
    about: "حول Voicebox",
    services: "الخدمات",
    hide: "إخفاء Voicebox",
    hide_others: "إخفاء الآخرين",
    quit: "إنهاء Voicebox",
    file: "ملف",
    close_window: "إغلاق النافذة",
    edit: "تحرير",
    undo: "تراجع",
    redo: "إعادة",
    cut: "قص",
    copy: "نسخ",
    paste: "لصق",
    select_all: "تحديد الكل",
    view: "عرض",
    fullscreen: "الدخول إلى ملء الشاشة",
    window: "نافذة",
    minimize: "تصغير",
    zoom: "تكبير/تصغير",
    help: "مساعدة",
    tray_open: "فتح Voicebox",
};

pub(crate) fn labels(lang: &str) -> &'static Labels {
    // "de", "de-AT", "ar-EG", … all map to their base language.
    match lang.split(['-', '_']).next().unwrap_or("") {
        "de" => &DE,
        "ar" => &AR,
        _ => &EN,
    }
}

/// Same layout as Tauri's `Menu::default` on macOS, with localized labels.
pub fn build<R: Runtime>(app: &AppHandle<R>, lang: &str) -> tauri::Result<Menu<R>> {
    let l = labels(lang);
    let pkg = app.package_info();
    let about_metadata = AboutMetadata {
        name: Some(pkg.name.clone()),
        version: Some(pkg.version.to_string()),
        copyright: app.config().bundle.copyright.clone(),
        authors: app.config().bundle.publisher.clone().map(|p| vec![p]),
        ..Default::default()
    };

    let app_menu = Submenu::with_items(
        app,
        pkg.name.clone(),
        true,
        &[
            &PredefinedMenuItem::about(app, Some(l.about), Some(about_metadata))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::services(app, Some(l.services))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::hide(app, Some(l.hide))?,
            &PredefinedMenuItem::hide_others(app, Some(l.hide_others))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::quit(app, Some(l.quit))?,
        ],
    )?;
    let file_menu = Submenu::with_items(
        app,
        l.file,
        true,
        &[&PredefinedMenuItem::close_window(
            app,
            Some(l.close_window),
        )?],
    )?;
    let edit_menu = Submenu::with_items(
        app,
        l.edit,
        true,
        &[
            &PredefinedMenuItem::undo(app, Some(l.undo))?,
            &PredefinedMenuItem::redo(app, Some(l.redo))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, Some(l.cut))?,
            &PredefinedMenuItem::copy(app, Some(l.copy))?,
            &PredefinedMenuItem::paste(app, Some(l.paste))?,
            &PredefinedMenuItem::select_all(app, Some(l.select_all))?,
        ],
    )?;
    let view_menu = Submenu::with_items(
        app,
        l.view,
        true,
        &[&PredefinedMenuItem::fullscreen(app, Some(l.fullscreen))?],
    )?;
    // The fixed ids let Tauri register these as NSApp's Window and Help menus.
    let window_menu = Submenu::with_id_and_items(
        app,
        WINDOW_SUBMENU_ID,
        l.window,
        true,
        &[
            &PredefinedMenuItem::minimize(app, Some(l.minimize))?,
            &PredefinedMenuItem::maximize(app, Some(l.zoom))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::close_window(app, Some(l.close_window))?,
        ],
    )?;
    let help_menu = Submenu::with_id_and_items(app, HELP_SUBMENU_ID, l.help, true, &[])?;

    Menu::with_items(
        app,
        &[
            &app_menu,
            &file_menu,
            &edit_menu,
            &view_menu,
            &window_menu,
            &help_menu,
        ],
    )
}

/// Rebuild the menu bar (and the menu bar icon's menu) in `lang`. Called by the frontend on startup and
/// whenever the user switches the display language.
#[tauri::command]
pub fn set_menu_language<R: Runtime>(app: AppHandle<R>, lang: String) -> Result<(), String> {
    crate::background::relabel_tray(&app, &lang);
    if !cfg!(target_os = "macos") {
        return Ok(());
    }
    persist_app_language(&app, &lang);
    let menu = build(&app, &lang).map_err(|e| e.to_string())?;
    app.set_menu(menu).map(|_| ()).map_err(|e| e.to_string())
}

/// Store `lang` as this app's AppleLanguages preference. AppKit reads it at
/// launch, so it applies to its own UI from the next start. Runs off the
/// calling thread because it shells out to `defaults`.
fn persist_app_language<R: Runtime>(app: &AppHandle<R>, lang: &str) {
    let base = lang.split(['-', '_']).next().unwrap_or("en").to_string();
    if !matches!(base.as_str(), "en" | "de" | "ar") {
        return;
    }
    let bundle_id = app.config().identifier.clone();
    std::thread::spawn(move || {
        let current = std::process::Command::new("defaults")
            .args(["read", &bundle_id, "AppleLanguages"])
            .output()
            .map(|o| String::from_utf8_lossy(&o.stdout).to_string())
            .unwrap_or_default();
        // `defaults read` prints the array as `(\n    de\n)`.
        let already_set = current
            .trim_matches(|c: char| c == '(' || c == ')' || c.is_whitespace())
            .trim_matches('"')
            == base;
        if already_set {
            return;
        }
        if let Err(e) = std::process::Command::new("defaults")
            .args(["write", &bundle_id, "AppleLanguages", "-array", &base])
            .status()
        {
            eprintln!("Could not store AppleLanguages={base}: {e}");
        }
    });
}
