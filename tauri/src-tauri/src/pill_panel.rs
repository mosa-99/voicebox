//! The dictate pill as a floating panel that shows on every Space,
//! fullscreen apps included (macOS).
//!
//! A plain NSWindow, even one that can join all Spaces, never appears in
//! another app's fullscreen Space. With a fullscreen app in front, the
//! chord showed the pill on the desktop Space instead. WebKit also holds
//! back `getUserMedia` until the page is visible, so nothing was recorded
//! until the user switched back to the desktop. Spotlight-style overlays
//! solve this with a non-activating NSPanel that is a full-screen auxiliary
//! window: it floats above whatever app is in front, on any Space, without
//! taking focus. tao only builds NSWindows, so the pill's window is
//! re-classed as such a panel right after it's created.

use objc::declare::ClassDecl;
use objc::runtime::{Class, Object, Sel, BOOL, NO};
use objc::{class, msg_send, sel, sel_impl};

/// NSWindowStyleMaskNonactivatingPanel: clicking the panel doesn't
/// activate Voicebox.
const NONACTIVATING_PANEL: u64 = 1 << 7;
/// NSWindowCollectionBehavior CanJoinAllSpaces | Stationary | IgnoresCycle
/// | FullScreenAuxiliary.
const COLLECTION_BEHAVIOR: u64 = (1 << 0) | (1 << 4) | (1 << 6) | (1 << 8);
/// NSStatusWindowLevel, above other apps' windows (fullscreen ones too).
const STATUS_WINDOW_LEVEL: i64 = 25;

extern "C" {
    fn object_setClass(obj: *mut Object, cls: *const Class) -> *const Class;
}

/// NSPanel subclass that never becomes key or main, so showing or clicking
/// the pill never takes the keyboard from the app being dictated into.
fn panel_class() -> &'static Class {
    if let Some(class) = Class::get("VoiceboxPillPanel") {
        return class;
    }
    extern "C" fn no(_: &Object, _: Sel) -> BOOL {
        NO
    }
    let mut decl = ClassDecl::new("VoiceboxPillPanel", class!(NSPanel))
        .expect("VoiceboxPillPanel is declared once");
    unsafe {
        decl.add_method(sel!(canBecomeKeyWindow), no as extern "C" fn(&Object, Sel) -> BOOL);
        decl.add_method(sel!(canBecomeMainWindow), no as extern "C" fn(&Object, Sel) -> BOOL);
    }
    decl.register()
}

/// Turn the pill's window into a floating, non-activating panel.
pub fn make_floating_panel(window: &tauri::WebviewWindow) {
    let target = window.clone();
    // AppKit must be called on the main thread; the pill is also built from
    // command handlers.
    let result = window.run_on_main_thread(move || {
        let Ok(ns_window) = target.ns_window() else {
            return;
        };
        let ns_window = ns_window as *mut Object;
        unsafe {
            object_setClass(ns_window, panel_class());
            let style: u64 = msg_send![ns_window, styleMask];
            let _: () = msg_send![ns_window, setStyleMask: style | NONACTIVATING_PANEL];
            // Panels hide when their app deactivates; the pill must stay up
            // while the user works in another app.
            let _: () = msg_send![ns_window, setHidesOnDeactivate: NO];
            let _: () = msg_send![ns_window, setCollectionBehavior: COLLECTION_BEHAVIOR];
            let _: () = msg_send![ns_window, setLevel: STATUS_WINDOW_LEVEL];
        }
    });
    if let Err(e) = result {
        eprintln!("Could not turn the dictate pill into a panel: {e}");
    }
}
