$log = 'D:\vee-mascot\make_hotkey.log'
try {
  $d = [Environment]::GetFolderPath('Desktop')
  $lnk = Join-Path $d 'Vee.lnk'
  $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
  $s.TargetPath = 'D:\Software\Pycharm\pythonw.exe'
  $s.Arguments = '"D:\vee-mascot\vee_toggle.pyw"'
  $s.WorkingDirectory = 'D:\vee-mascot'
  $s.Hotkey = 'CTRL+ALT+M'
  $s.Description = 'Start or close Vee (Ctrl+Alt+M)'
  $s.Save()
  $chk = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
  "created: $lnk exists=$(Test-Path $lnk) hotkey=$($chk.Hotkey) target=$($chk.TargetPath)" | Out-File $log -Encoding utf8
} catch { "error: $_" | Out-File $log -Encoding utf8 }
