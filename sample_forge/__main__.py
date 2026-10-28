"""CLI: python -m sample_forge gen|search|export|budget|voices|serve"""
import argparse

from .core import DEFAULT_VOICE, Forge, Req
from .eleven import Eleven

ap = argparse.ArgumentParser(prog="sample_forge")
sub = ap.add_subparsers(dest="cmd", required=True)

g = sub.add_parser("gen", help="generar samples (sfx o vox)")
g.add_argument("kind", choices=["sfx", "vox"])
g.add_argument("prompt")
g.add_argument("-n", type=int, default=1, help="variantes")
g.add_argument("-d", "--duration", type=float, help="segundos (sfx)")
g.add_argument("--loop", action="store_true")
g.add_argument("--voice", default=DEFAULT_VOICE)
g.add_argument("--tags", nargs="*", default=[])
g.add_argument("--dry-run", action="store_true", help="solo estima el costo")

s = sub.add_parser("search", help="buscar en la librería")
s.add_argument("q", nargs="?", default="")
s.add_argument("--kind", choices=["sfx", "vox"])
s.add_argument("--note", help="A = cualquier octava, A4 = exacta")
s.add_argument("--max-dur", type=float)

e = sub.add_parser("export", help="copiar samples a una carpeta (p. ej. tu Places de Ableton)")
e.add_argument("dest")
e.add_argument("q", nargs="?", default="")
e.add_argument("--kind", choices=["sfx", "vox"])
e.add_argument("--note")
e.add_argument("--max-dur", type=float)

sub.add_parser("budget", help="créditos usados este mes")
sub.add_parser("voices", help="voces disponibles en tu cuenta")
sv = sub.add_parser("serve", help="API + web en http://127.0.0.1:8000")
sv.add_argument("--port", type=int, default=8000)
a = ap.parse_args()


def row(x):
    return (f"{x['id']}  {x['kind']:3}  {x['duration']:5.1f}s  {x['note'] or '-':4}  "
            f"{x['peak_db']:6.1f} dBFS  {x['prompt'][:50]}")


if a.cmd == "serve":
    import uvicorn
    uvicorn.run("sample_forge.api:app", host="127.0.0.1", port=a.port)
elif a.cmd == "voices":
    for id, name in Eleven().voices():
        print(id, name)
else:
    forge = Forge(Eleven())
    if a.cmd == "gen":
        r = Req(kind=a.kind, prompt=a.prompt, n=a.n, duration=a.duration, loop=a.loop, voice=a.voice, tags=a.tags)
        est = forge.estimate(r)
        print(f"{est['new']} nuevas, {est['cached']} en caché: ~{est['credits']} créditos "
              f"(quedan {est['left']} de {est['budget']} este mes)")
        if not a.dry_run:
            for x in forge.generate(r):
                print(("caché " if x["cached"] else "nuevo ") + row(x))
    elif a.cmd == "search":
        for x in forge.db.search(a.q, a.kind, a.note, a.max_dur):
            print(row(x))
    elif a.cmd == "export":
        found = forge.db.search(a.q, a.kind, a.note, a.max_dur, limit=10_000)
        for p in forge.export([x["id"] for x in found], a.dest):
            print(p)
    elif a.cmd == "budget":
        print(forge.status())
