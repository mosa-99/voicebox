//! Running in the background.
//!
//! With "Run in background" on (the default), closing the main window only
//! hides it: the server, the global dictation shortcut and the dictate pill
//! keep working, and on macOS the Dock icon goes away so Voicebox lives in the
//! menu bar like other utility apps (see tray.rs). The menu bar icon, or
//! opening the app again, brings the window back; Quit (or ⌘Q) really exits.
//!
//! Launched with `--hidden` (the login item does this), the window starts
//! hidden. Linux keeps its old behavior: closing the window quits.

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::{AppHandle, Emitter, Manager, Runtime};

pub const MAIN_WINDOW_LABEL: &str = "main";
/// Command-line flag for starting without showing the main window.
pub const HIDDEN_ARG: &str = "--hidden";

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

/// Show the main window on a given page ("/captures", "/settings", …). The
/// frontend router listens for `tray:navigate`.
pub fn show_main_window_at<R: Runtime>(app: &AppHandle<R>, path: &str) {
    show_main_window(app);
    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        let _ = window.emit("tray:navigate", path);
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
