#include <assert.h>
#include <stdnoreturn.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <windows.h>

static noreturn void fatal_error(const wchar_t *msg)
{
	// Ideally this would use GetLastError, but FormatMessage seems really complicated
	MessageBoxW(NULL, msg, L"Porcupine cannot start", MB_OK | MB_ICONERROR);
	exit(1);
}

typedef int(WINAPI *PyMainProc)(int argc, wchar_t **argv);

int wmain(int argc, wchar_t **argv)
{
	wchar_t *launcherpath = calloc(sizeof(launcherpath[0]), MAX_PATH);
	if (!launcherpath)
		fatal_error(L"allocating memory failed");

	if (GetModuleFileNameW(NULL, launcherpath, MAX_PATH-1) <= 0)
		fatal_error(L"GetModuleFileNameW(NULL, ...) failed");

	// ...\Porcupine\Python\Porcupine.exe --> ...\Porcupine\launch.pyw
	*wcsrchr(launcherpath, L'\\') = L'\0';
	*wcsrchr(launcherpath, L'\\') = L'\0';
	wcscat(launcherpath, L"\\launch.pyw");

	HMODULE pydll = LoadLibraryW(L"python3.dll");
	if (!pydll)
		fatal_error(L"Can't load python3.dll");

	PyMainProc Py_Main = (PyMainProc)GetProcAddress(pydll, "Py_Main");
	if (!Py_Main)
		fatal_error(L"Can't find Py_Main() in python3.dll");

	// argv[argc] is NULL
	wchar_t **myargv = malloc(sizeof(myargv[0]) * (argc+2));
	myargv[0] = argv[0];
	myargv[1] = launcherpath;
	memcpy(&myargv[2], &argv[1], sizeof(myargv[0]) * argc);

	for (int i = 0; i < argc+1; i++)
		MessageBoxW(NULL, myargv[i], L"my arg", MB_OK);

	// not freeing the resources, will be freed on exit anyway
	return Py_Main(argc+1, myargv);
}
