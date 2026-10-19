//! Menu bar icon and running in the background.
//!
//! With "Run in background" on (the default), closing the main window only
//! hides it: the server, the global dictation shortcut and the dictate pill
//! keep working, and on macOS the Dock icon goes away so Voicebox lives in the
//! menu bar like other utility apps. The menu bar icon, or opening the app
//! again, brings the window back; its Quit item (or ⌘Q) really exits.
//!
//! Launched with `--hidden` (the login item does this), the window starts
//! hidden. Linux keeps its old behavior: closing the window quits.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Manager, Runtime};

pub const MAIN_WINDOW_LABEL: &str = "main";
/// Command-line flag for starting without showing the main window.
pub const HIDDEN_ARG: &str = "--hidden";

const TRAY_ID: &str = "voicebox";
const OPEN_ITEM_ID: &str = "tray-open";
const QUIT_ITEM_ID: &str = "tray-quit";

/// Mirrors the "Run in background" setting; the frontend syncs it on startup
/// and whenever it changes.
static RUN_IN_BACKGROUND: AtomicBool = AtomicBool::new(true);

/// Whether closing the main window should hide it instead of closing it.
pub fn runs_in_background() -> bool {
    !cfg!(target_os = "linux") && RUN_IN_BACKGROUND.load(Ordering::SeqCst)
}

#[tauri::command]
pub fn set_run_in_background(enabled: bool) {
    RUN_IN_BACKGROUND.store(enabled, Ordering::SeqCst);
}

/// True when this launch asked to start without a visible window.
pub fn started_hidden() -> bool {
    std::env::args().any(|arg| arg == HIDDEN_ARG)
}

/// Show and focus the main window (and the Dock icon on macOS).
pub fn show_main_window<R: Runtime>(app: &AppHandle<R>) {
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);
    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

/// Hide the main window; on macOS also drop the Dock icon so only the menu
/// bar icon remains.
pub fn hide_main_window<R: Runtime>(app: &AppHandle<R>) {
    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        let _ = window.hide();
    }
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Accessory);
}

fn tray_menu<R: Runtime>(app: &AppHandle<R>, lang: &str) -> tauri::Result<Menu<R>> {
    let labels = crate::app_menu::labels(lang);
    Menu::with_items(
        app,
        &[
            &MenuItem::with_id(app, OPEN_ITEM_ID, labels.tray_open, true, None::<&str>)?,
            &PredefinedMenuItem::separator(app)?,
            &MenuItem::with_id(app, QUIT_ITEM_ID, labels.quit, true, None::<&str>)?,
        ],
    )
}

/// Add the menu bar icon. Not on Linux, where the window close quits anyway
/// and a tray needs libappindicator.
pub fn create_tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    if cfg!(target_os = "linux") {
        return Ok(());
    }
    let menu = tray_menu(app, "en")?;
    let builder = TrayIconBuilder::with_id(TRAY_ID)
        .tooltip("Voicebox")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id().as_ref() {
            OPEN_ITEM_ID => show_main_window(app),
            QUIT_ITEM_ID => app.exit(0),
            _ => {}
        });
    // A black template image lets macOS tint it for light and dark menu bars.
    #[cfg(target_os = "macos")]
    let builder = builder
        .icon(tauri::image::Image::from_bytes(include_bytes!(
            "../icons/tray-template@2x.png"
        ))?)
        .icon_as_template(true);
    #[cfg(not(target_os = "macos"))]
    let builder = match app.default_window_icon() {
        Some(icon) => builder.icon(icon.clone()),
        None => builder,
    };
    builder.build(app)?;
    Ok(())
}

/// Relabel the menu bar icon's menu; called together with the app menu.
pub fn relabel_tray<R: Runtime>(app: &AppHandle<R>, lang: &str) {
    if let Some(tray) = app.tray_by_id(TRAY_ID) {
        if let Ok(menu) = tray_menu(app, lang) {
            let _ = tray.set_menu(Some(menu));
        }
    }
}
