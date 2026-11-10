#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#define PROJECT64_FULLSCREEN_COMMAND 4173

static HWND game_window;
static unsigned int matches;

static BOOL CALLBACK find_game(HWND window, LPARAM unused)
{
    DWORD pid;
    WCHAR path[MAX_PATH];
    DWORD length = MAX_PATH;
    HANDLE process;
    WCHAR *name;
    (void)unused;
    if (!IsWindowVisible(window) || GetWindow(window, GW_OWNER))
        return TRUE;
    GetWindowThreadProcessId(window, &pid);
    process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!process)
        return TRUE;
    if (QueryFullProcessImageNameW(process, 0, path, &length)) {
        name = wcsrchr(path, L'\\');
        if (name && _wcsicmp(name + 1, L"Project64.exe") == 0) {
            game_window = window;
            matches++;
        }
    }
    CloseHandle(process);
    return TRUE;
}

static BOOL CALLBACK hide_status(HWND window, LPARAM unused)
{
    WCHAR name[128];
    (void)unused;
    GetClassNameW(window, name, 128);
    if (_wcsicmp(name, L"msctls_statusbar32") == 0)
        ShowWindow(window, SW_HIDE);
    return TRUE;
}

int main(int argc, char **argv)
{
    MONITORINFO monitor = {0};
    LONG_PTR style;
    LONG_PTR extended;
    RECT actual;
    SetProcessDPIAware();
    if (argc == 2 && (!strcmp(argv[1], "--configure") ||
                      !strcmp(argv[1], "--windowed"))) {
        HKEY key;
        DWORD width;
        DWORD height;
        DWORD window_width = 640;
        DWORD window_height = 480;
        LONG result;
        POINT origin = {0, 0};
        monitor.cbSize = sizeof(monitor);
        if (!GetMonitorInfoW(MonitorFromPoint(origin, MONITOR_DEFAULTTOPRIMARY),
                             &monitor)) {
            fprintf(stderr, "Cannot read primary monitor: %lu\n", GetLastError());
            return 1;
        }
        width = !strcmp(argv[1], "--windowed") ? 640 :
            (DWORD)(monitor.rcMonitor.right - monitor.rcMonitor.left);
        height = !strcmp(argv[1], "--windowed") ? 480 :
            (DWORD)(monitor.rcMonitor.bottom - monitor.rcMonitor.top);
        result = RegCreateKeyExW(
            HKEY_CURRENT_USER, L"Software\\Mudlord\\Rice's Video Plugin\\Stable",
            0, NULL, 0, KEY_SET_VALUE, NULL, &key, NULL);
        if (result != ERROR_SUCCESS) {
            fprintf(stderr, "Cannot open Rice settings: %ld\n", result);
            return 1;
        }
        result = RegSetValueExW(key, L"WinModeWidth", 0, REG_DWORD,
                                (BYTE *)&window_width, sizeof(window_width));
        if (result == ERROR_SUCCESS)
            result = RegSetValueExW(key, L"WinModeHeight", 0, REG_DWORD,
                                    (BYTE *)&window_height, sizeof(window_height));
        if (result == ERROR_SUCCESS && strcmp(argv[1], "--windowed"))
            result = RegSetValueExW(key, L"FulScreenWidth", 0, REG_DWORD,
                                    (BYTE *)&width, sizeof(width));
        if (result == ERROR_SUCCESS && strcmp(argv[1], "--windowed"))
            result = RegSetValueExW(key, L"FulScreenHeight", 0, REG_DWORD,
                                    (BYTE *)&height, sizeof(height));
        RegCloseKey(key);
        if (result != ERROR_SUCCESS) {
            fprintf(stderr, "Cannot set Rice rendering size: %ld\n", result);
            return 1;
        }
        printf("Rice rendering size: %lu x %lu\n", width, height);
        return 0;
    }
    if (argc != 1) {
        fprintf(stderr, "Usage: borderless.exe [--configure|--windowed]\n");
        return 1;
    }
    for (unsigned int attempt = 0; attempt < 200; attempt++) {
        matches = 0;
        game_window = NULL;
        EnumWindows(find_game, 0);
        if (matches)
            break;
        Sleep(100);
    }
    if (matches != 1) {
        fprintf(stderr, "Expected one Project64 game window; found %u.\n", matches);
        return 1;
    }
    if (GetMenu(game_window)) {
        DWORD_PTR result;
        HWND status = FindWindowExW(game_window, NULL, L"msctls_statusbar32", NULL);
        if (!status || !IsWindowVisible(status)) {
            fprintf(stderr, "Expected Project64's windowed status bar before fullscreen.\n");
            return 1;
        }
        SetForegroundWindow(game_window);
        if (!SendMessageTimeoutW(game_window, WM_COMMAND,
                                 PROJECT64_FULLSCREEN_COMMAND, 0,
                                 SMTO_ABORTIFHUNG, 15000, &result)) {
            fprintf(stderr, "Cannot resize Rice's native viewport: %lu\n",
                    GetLastError());
            return 1;
        }
        /* Project64 queues the command on its emulation thread. */
        for (unsigned int attempt = 0; attempt < 150 && IsWindowVisible(status);
             attempt++)
            Sleep(100);
        if (!SendMessageTimeoutW(game_window, WM_NULL, 0, 0,
                                 SMTO_ABORTIFHUNG, 15000, &result)) {
            fprintf(stderr, "Project64 did not finish updating its fullscreen viewport.\n");
            return 1;
        }
        if (!IsWindow(game_window) || IsWindowVisible(status)) {
            fprintf(stderr, "Project64 did not complete its native fullscreen transition.\n");
            return 1;
        }
    }
    monitor.cbSize = sizeof(monitor);
    if (!GetMonitorInfoW(MonitorFromWindow(game_window, MONITOR_DEFAULTTONEAREST),
                         &monitor)) {
        fprintf(stderr, "Cannot read game monitor: %lu\n", GetLastError());
        return 1;
    }
    style = GetWindowLongPtrW(game_window, GWL_STYLE);
    extended = GetWindowLongPtrW(game_window, GWL_EXSTYLE);
    SetLastError(0);
    if (!SetWindowLongPtrW(game_window, GWL_STYLE,
                          (style & ~WS_OVERLAPPEDWINDOW) | WS_POPUP) &&
        GetLastError()) {
        fprintf(stderr, "Cannot remove game frame: %lu\n", GetLastError());
        return 1;
    }
    SetLastError(0);
    if (!SetWindowLongPtrW(game_window, GWL_EXSTYLE,
                          extended & ~(WS_EX_CLIENTEDGE | WS_EX_WINDOWEDGE |
                                       WS_EX_DLGMODALFRAME | WS_EX_STATICEDGE)) &&
        GetLastError()) {
        fprintf(stderr, "Cannot remove game edges: %lu\n", GetLastError());
        return 1;
    }
    if (!SetMenu(game_window, NULL)) {
        fprintf(stderr, "Cannot hide game menu: %lu\n", GetLastError());
        return 1;
    }
    EnumChildWindows(game_window, hide_status, 0);
    if (!SetWindowPos(game_window, HWND_TOP,
                      monitor.rcMonitor.left, monitor.rcMonitor.top,
                      monitor.rcMonitor.right - monitor.rcMonitor.left,
                      monitor.rcMonitor.bottom - monitor.rcMonitor.top,
                      SWP_FRAMECHANGED | SWP_SHOWWINDOW)) {
        fprintf(stderr, "Cannot resize game: %lu\n", GetLastError());
        return 1;
    }
    if (!GetWindowRect(game_window, &actual) ||
        !EqualRect(&actual, &monitor.rcMonitor)) {
        fprintf(stderr, "Project64 did not retain the fullscreen monitor size.\n");
        return 1;
    }
    printf("Borderless fullscreen: %ld x %ld\n",
           actual.right - actual.left, actual.bottom - actual.top);
    return 0;
}
