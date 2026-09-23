//! Single instance guard using Windows Named Mutex (L03).

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
pub struct SingleInstanceGuard;

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
        let _ = mutex_name;
        Some(SingleInstanceGuard)
    }
}
