#include <assert.h>
#include <stdnoreturn.h>
#include <stdlib.h>
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
	MessageBoxW(NULL, L"asd 1", L"asd1", MB_OK);
	wchar_t *launcherpath = calloc(sizeof(launcherpath[0]), MAX_PATH);
	MessageBoxW(NULL, L"asd 2", L"asd2", MB_OK);
	if (!launcherpath)
		fatal_error(L"allocating memory failed");
	MessageBoxW(NULL, L"asd 3", L"asd3", MB_OK);

	if (GetModuleFileNameW(NULL, launcherpath, MAX_PATH-1) <= 0)
		fatal_error(L"GetModuleFileNameW(NULL, ...) failed");
	MessageBoxW(NULL, L"asd 4", L"adsd4", MB_OK);

	// ...\Porcupine\Python\Porcupine.exe --> ...\Porcupine\launch.pyw
	MessageBoxW(NULL, launcherpath, L"asd5", MB_OK);
	*wcsrchr(launcherpath, L'\\') = L'\0';
	MessageBoxW(NULL, launcherpath, L"asd6", MB_OK);
	*wcsrchr(launcherpath, L'\\') = L'\0';
	MessageBoxW(NULL, launcherpath, L"asd7", MB_OK);
	wcscat(launcherpath, L"\\launch.pyw");
	MessageBoxW(NULL, launcherpath, L"asd8", MB_OK);

	HMODULE pydll = LoadLibraryW(L"python3.dll");
	MessageBoxW(NULL, L"asd 9", L"asd9", MB_OK);
	if (!pydll)
		fatal_error(L"Can't load python3.dll");
	MessageBoxW(NULL, L"asd 10", L"asd10", MB_OK);

	PyMainProc Py_Main = (PyMainProc)GetProcAddress(pydll, "Py_Main");
	MessageBoxW(NULL, L"asd 11", L"asd11", MB_OK);
	if (!Py_Main)
		fatal_error(L"Can't find Py_Main() in python3.dll");

	MessageBoxW(NULL, L"asd 12", L"asd12", MB_OK);
	wchar_t **myargv = calloc(sizeof(myargv[0]), 3);  // argv should end with NULL
	myargv[0] = argv[0];
	myargv[1] = launcherpath;
	for (int i = 0; i < 3; i++)
		MessageBoxW(NULL, myargv[i] ? myargv[i] : L"NULL", L"argument", MB_OK);

	// not freeing the resources, will be freed on exit anyway
	MessageBoxW(NULL, L"calling main", L"main START", MB_OK);
	int r = Py_Main(2, myargv);
	wchar_t msg[100];
	swprintf(msg, 40, L"Py_Main(%d, ...) returned %d", 2, r);
	MessageBoxW(NULL, msg, L"main DONE", MB_OK);
	return r;
}
