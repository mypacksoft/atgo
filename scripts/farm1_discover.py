"""Discover what's already running on farm1 before installing ATGO."""
import paramiko, base64

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("farm1.mypacksoft.com", 29812, "administrator",
          "Makiut128600911994@@@@", timeout=15,
          look_for_keys=False, allow_agent=False)

def cmd(s, ps=False, label=None):
    print(f"\n=== {label or s[:80]} ===")
    if ps:
        enc = base64.b64encode(s.encode("utf-16-le")).decode()
        s = f"powershell -NoProfile -EncodedCommand {enc}"
    stdin, stdout, stderr = c.exec_command(s, timeout=30)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out: print(out.strip()[:3000])
    if err and "CLIXML" not in err: print("STDERR:", err[:300])

# ---- OS / hardware ----
cmd("systeminfo | findstr /C:\"OS Name\" /C:\"OS Version\" /C:\"System Type\" "
    "/C:\"Total Physical Memory\" /C:\"Available Physical Memory\" "
    "/C:\"Domain\" /C:\"Logon Server\"", label="OS / hardware")

cmd("wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /format:list",
    label="CPU")

cmd("wmic logicaldisk get Caption,FreeSpace,Size,VolumeName /format:list",
    label="Disks")

# ---- Domain controller? ----
cmd("(Get-WindowsFeature -Name AD-Domain-Services).Installed", ps=True,
    label="Is AD DS feature installed?")
cmd("Get-Service NTDS,DNS,KDC,Netlogon -ErrorAction SilentlyContinue "
    "| Select Name,Status,StartType | Format-Table -AutoSize | Out-String -Width 200",
    ps=True, label="DC services state")

# ---- Already-listening ports ----
cmd("netstat -ano | findstr LISTEN | findstr /R \":80 :443 :3000 :8000 :8001 \"\":1433\" \":1434\" \":1438\" \":5432\" \":6379\" \":29812\"",
    label="Listening on common ATGO/SQL ports")

# ---- Installed runtimes ----
cmd("Get-Command python,python3,node,npm,git,docker,caddy,psql,nssm "
    "-ErrorAction SilentlyContinue | Select Name,Source,Version "
    "| Format-Table -AutoSize | Out-String -Width 200",
    ps=True, label="Runtimes already on PATH")

# ---- SQL Server ----
cmd("Get-Service MSSQL* -ErrorAction SilentlyContinue "
    "| Select Name,Status,StartType | Format-Table -AutoSize | Out-String -Width 200",
    ps=True, label="SQL Server services")

# ---- Postgres ----
cmd("Get-Service postgresql* -ErrorAction SilentlyContinue "
    "| Select Name,Status | Format-Table -AutoSize | Out-String -Width 200",
    ps=True, label="Postgres service")

# ---- IIS / web servers ----
cmd("Get-Service W3SVC,nginx,caddy -ErrorAction SilentlyContinue "
    "| Select Name,Status | Format-Table -AutoSize | Out-String -Width 200",
    ps=True, label="Web server services")

# ---- Docker ----
cmd("Get-Service docker -ErrorAction SilentlyContinue "
    "| Select Name,Status; "
    "Get-WindowsFeature -Name Hyper-V,Containers | Select Name,InstallState | Format-Table",
    ps=True, label="Docker / Hyper-V / Containers feature")

# ---- ATGO domain DNS ----
cmd("Resolve-DnsName atgo.io -ErrorAction SilentlyContinue | Select Name,Type,IPAddress | Format-Table -AutoSize | Out-String -Width 100",
    ps=True, label="DNS for atgo.io from this server")

# ---- Outbound internet ----
cmd("Test-NetConnection 1.1.1.1 -Port 443 -WarningAction SilentlyContinue "
    "| Select TcpTestSucceeded,RemoteAddress,RemotePort | Format-List",
    ps=True, label="Outbound HTTPS reachability")

c.close()
print("\n=== done ===")
