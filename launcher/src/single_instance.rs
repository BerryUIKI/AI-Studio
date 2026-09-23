//! Single instance guard: Windows Named Mutex on Windows, Unix domain socket on macOS/Linux (L03, M12).

#[cfg(windows)]
pub struct SingleInstanceGuard {
    handle: *mut std::ffi::c_void,
}

#[cfg(windows)]
extern "system" {
    fn CreateMutexW(
        lpMutexAttributes: *const std::ffi::c_void,
        bInitialOwner: i32,
        lpName: *const u16,
    ) -> *mut std::ffi::c_void;
    fn CloseHandle(hObject: *mut std::ffi::c_void) -> i32;
    fn GetLastError() -> u32;
}

#[cfg(windows)]
const ERROR_ALREADY_EXISTS: u32 = 183;

#[cfg(windows)]
impl Drop for SingleInstanceGuard {
    fn drop(&mut self) {
        if !self.handle.is_null() {
            unsafe {
                CloseHandle(self.handle);
            }
        }
    }
}

#[cfg(not(windows))]
pub struct SingleInstanceGuard {
    _listener: std::os::unix::net::UnixListener,
    sock_path: std::path::PathBuf,
}

#[cfg(not(windows))]
impl Drop for SingleInstanceGuard {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.sock_path);
    }
}

/// Try to acquire the single instance lock.
/// Returns `Some(guard)` if this is the only instance, or `None` if an instance is already running.
pub fn try_acquire_single_instance(mutex_name: &str) -> Option<SingleInstanceGuard> {
    #[cfg(windows)]
    {
        use std::ffi::OsStr;
        use std::os::windows::ffi::OsStrExt;

        let wide: Vec<u16> = OsStr::new(mutex_name)
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();

        unsafe {
            let handle = CreateMutexW(std::ptr::null(), 1, wide.as_ptr());
            if handle.is_null() {
                return None;
            }

            if GetLastError() == ERROR_ALREADY_EXISTS {
                CloseHandle(handle);
                return None;
            }

            Some(SingleInstanceGuard { handle })
        }
    }

    #[cfg(not(windows))]
    {
        use std::env;
        use std::os::unix::net::{UnixListener, UnixStream};

        let tmp_dir = env::var_os("TMPDIR")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|| std::path::PathBuf::from("/tmp"));
        let clean_name = mutex_name.replace('\\', "_").replace('/', "_");
        let sock_path = tmp_dir.join(format!("{}.sock", clean_name));

        // If file exists, test if a live process is listening
        if sock_path.exists() {
            if UnixStream::connect(&sock_path).is_ok() {
                // Active process exists
                return None;
            }
            // Stale socket, remove it
            let _ = std::fs::remove_file(&sock_path);
        }

        match UnixListener::bind(&sock_path) {
            Ok(listener) => Some(SingleInstanceGuard {
                _listener: listener,
                sock_path,
            }),
            Err(_) => None,
        }
    }
}

/// Cross-platform browser launcher (Windows cmd start, macOS open, Linux xdg-open).
pub fn open_browser(url: &str) {
    #[cfg(windows)]
    {
        let _ = std::process::Command::new("cmd").args(["/c", "start", "", url]).spawn();
    }
    #[cfg(target_os = "macos")]
    {
        let _ = std::process::Command::new("open").arg(url).spawn();
    }
    #[cfg(all(not(windows), not(target_os = "macos")))]
    {
        let _ = std::process::Command::new("xdg-open").arg(url).spawn();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_single_instance_acquisition() {
        let name = "Berry_Test_Single_Instance_Mutex";
        let guard1 = try_acquire_single_instance(name);
        assert!(guard1.is_some());

        // Second acquisition while guard1 is held should return None
        let guard2 = try_acquire_single_instance(name);
        assert!(guard2.is_none());

        // Dropping guard1 should allow subsequent acquisition
        drop(guard1);
        let guard3 = try_acquire_single_instance(name);
        assert!(guard3.is_some());
    }
}
