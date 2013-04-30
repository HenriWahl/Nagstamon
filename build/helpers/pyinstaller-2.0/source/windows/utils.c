/*
 * Bootloader for a packed executable.
 * Copyright (C) 2009, Lorenzo Masini
 * Based on previous work under copyright (c) 2002 McMillan Enterprises, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * In addition to the permissions in the GNU General Public License, the
 * authors give you unlimited permission to link or embed the compiled
 * version of this file into combinations with other programs, and to
 * distribute those combinations without any restriction coming from the
 * use of this file. (The General Public License restrictions do apply in
 * other respects; for example, they cover modification of the file, and
 * distribution when not linked into a combine executable.)
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
 */
#define _WIN32_WINNT 0x0500
#include "utils.h"
#include <windows.h>
#include <commctrl.h> // InitCommonControls
#include <signal.h>
#include <memory.h>
#include <string.h>

char* basename (char *path)
{
  /* Search for the last directory separator in PATH.  */
  char *basename = strrchr (path, '\\');
  if (!basename) basename = strrchr (path, '/');

  /* If found, return the address of the following character,
     or the start of the parameter passed in.  */
  return basename ? ++basename : (char*)path;
}

static HANDLE hCtx = INVALID_HANDLE_VALUE;
static ULONG_PTR actToken;

#ifndef STATUS_SXS_EARLY_DEACTIVATION
#define STATUS_SXS_EARLY_DEACTIVATION 0xC015000F
#endif

int IsXPOrLater(void)
{
    OSVERSIONINFO osvi;

    ZeroMemory(&osvi, sizeof(OSVERSIONINFO));
    osvi.dwOSVersionInfoSize = sizeof(OSVERSIONINFO);

    GetVersionEx(&osvi);

    return ((osvi.dwMajorVersion > 5) ||
       ((osvi.dwMajorVersion == 5) && (osvi.dwMinorVersion >= 1)));
}

int CreateActContext(char *workpath, char *thisfile)
{
    char manifestpath[_MAX_PATH + 1];
    ACTCTX ctx;
    BOOL activated;
    HANDLE k32;
    HANDLE (WINAPI *CreateActCtx)(PACTCTX pActCtx);
    BOOL (WINAPI *ActivateActCtx)(HANDLE hActCtx, ULONG_PTR *lpCookie);

    // If not XP, nothing to do -- return OK
    if (!IsXPOrLater())
        return 1;

    /* Setup activation context */
    strcpy(manifestpath, workpath);
    strcat(manifestpath, basename(thisfile));
    strcat(manifestpath, ".manifest");
    VS("manifestpath: %s\n", manifestpath);

    k32 = LoadLibrary("kernel32");
    CreateActCtx = (void*)GetProcAddress(k32, "CreateActCtxA");
    ActivateActCtx = (void*)GetProcAddress(k32, "ActivateActCtx");

    if (!CreateActCtx || !ActivateActCtx)
    {
        VS("Cannot find CreateActCtx/ActivateActCtx exports in kernel32.dll\n");
        return 0;
    }

    ZeroMemory(&ctx, sizeof(ctx));
    ctx.cbSize = sizeof(ACTCTX);
    ctx.lpSource = manifestpath;

    hCtx = CreateActCtx(&ctx);
    if (hCtx != INVALID_HANDLE_VALUE)
    {
        VS("Activation context created\n");
        activated = ActivateActCtx(hCtx, &actToken);
        if (activated)
        {
            VS("Activation context activated\n");
            return 1;
        }
    }

    hCtx = INVALID_HANDLE_VALUE;
    VS("Error activating the context\n");
    return 0;
}

void ReleaseActContext(void)
{
    void (WINAPI *ReleaseActCtx)(HANDLE);
    BOOL (WINAPI *DeactivateActCtx)(DWORD dwFlags, ULONG_PTR ulCookie);
    HANDLE k32;

    if (!IsXPOrLater())
        return;

    k32 = LoadLibrary("kernel32");
    ReleaseActCtx = (void*)GetProcAddress(k32, "ReleaseActCtx");
    DeactivateActCtx = (void*)GetProcAddress(k32, "DeactivateActCtx");
    if (!ReleaseActCtx || !DeactivateActCtx)
    {
        VS("Cannot find ReleaseActCtx/DeactivateActCtx exports in kernel32.dll\n");
        return;
    }
    __try
    {
        VS("Deactivating activation context\n");
        if (!DeactivateActCtx(0, actToken))
            VS("Error deactivating context!\n!");

        VS("Releasing activation context\n");
        if (hCtx != INVALID_HANDLE_VALUE)
            ReleaseActCtx(hCtx);
        VS("Done\n");
    }
    __except (STATUS_SXS_EARLY_DEACTIVATION)
    {
    	VS("XS early deactivation; somebody left the activation context dirty, let's ignore the problem\n");
    }
}

void init_launcher(void)
{
	InitCommonControls();
}

int get_thisfile(char *thisfile, const char *programname)
{
	if (!GetModuleFileNameA(NULL, thisfile, _MAX_PATH)) {
		FATALERROR("System error - unable to load!");
		return -1;
	}

	return 0;
}

int get_thisfilew(LPWSTR thisfilew)
{
	if (!GetModuleFileNameW(NULL, thisfilew, _MAX_PATH)) {
		FATALERROR("System error - unable to load!");
		return -1;
	}

	return 0;
}

void get_homepath(char *homepath, const char *thisfile)
{
	char *p = NULL;

	strcpy(homepath, thisfile);
	for (p = homepath + strlen(homepath); *p != '\\' && p >= homepath + 2; --p);
	*++p = '\0';
}

void get_archivefile(char *archivefile, const char *thisfile)
{
	strcpy(archivefile, thisfile);
	strcpy(archivefile + strlen(archivefile) - 3, "pkg");
}

int set_environment(const ARCHIVE_STATUS *status)
{
	return 0;
}

int spawn(LPWSTR thisfile)
{
	SECURITY_ATTRIBUTES sa;
	STARTUPINFOW si;
	PROCESS_INFORMATION pi;
	int rc = 0;

	// the parent process should ignore all signals it can
	signal(SIGABRT, SIG_IGN);
	signal(SIGINT, SIG_IGN);
	signal(SIGTERM, SIG_IGN);
	signal(SIGBREAK, SIG_IGN);

	VS("Setting up to run child\n");
	sa.nLength = sizeof(sa);
	sa.lpSecurityDescriptor = NULL;
	sa.bInheritHandle = TRUE;
	GetStartupInfoW(&si);
	si.lpReserved = NULL;
	si.lpDesktop = NULL;
	si.lpTitle = NULL;
	si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
	si.wShowWindow = SW_NORMAL;
	si.hStdInput = (void*)_get_osfhandle(fileno(stdin));
	si.hStdOutput = (void*)_get_osfhandle(fileno(stdout));
	si.hStdError = (void*)_get_osfhandle(fileno(stderr));

	VS("Creating child process\n");
	if (CreateProcessW(
			thisfile, // pointer to name of executable module
			GetCommandLineW(),  // pointer to command line string
			&sa,  // pointer to process security attributes
			NULL,  // pointer to thread security attributes
			TRUE,  // handle inheritance flag
			0,  // creation flags
			NULL,  // pointer to new environment block
			NULL,  // pointer to current directory name
			&si,  // pointer to STARTUPINFO
			&pi  // pointer to PROCESS_INFORMATION
			)) {
		VS("Waiting for child process to finish...\n");
		WaitForSingleObject(pi.hProcess, INFINITE);
		GetExitCodeProcess(pi.hProcess, (unsigned long *)&rc);
	} else {
		FATALERROR("Error creating child process!\n");
		rc = -1;
	}
	return rc;
}
