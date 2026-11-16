"""Procedural fantasy sound synthesis (pure Python, no dependencies).

Primitives: bells, struck metal, brass/war horns, drums, filtered noise, reverb.
`event_sounds(style, root)` returns {event_name: samples} for the "crown" or "ember" style.
"""
import math
import random
import struct
import wave

SR = 44100


# ---------------------------------------------------------------- buffers
def silence(dur):
    return [0.0] * int(dur * SR)


def mix(length, *parts):
    """parts: (offset_seconds, samples, gain)."""
    out = [0.0] * int(length * SR)
    for off, x, g in parts:
        o = int(off * SR)
        for i, v in enumerate(x[:max(0, len(out) - o)]):
            out[o + i] += v * g
    return out


def normalize(x, peak=0.85):
    m = max((abs(v) for v in x), default=0) or 1
    return [v * peak / m for v in x]


def fade_out(x, dur=0.05):
    n = min(len(x), int(dur * SR))
    for i in range(n):
        x[-n + i] *= 1 - i / n
    return x


def saturate(x, drive):
    k = math.tanh(drive)
    return [math.tanh(v * drive) / k for v in x]


def lowpass(x, cutoff):
    a = 1 - math.exp(-2 * math.pi * cutoff / SR)
    y, out = 0.0, []
    for v in x:
        y += a * (v - y)
        out.append(y)
    return out


def highpass(x, cutoff):
    lp = lowpass(x, cutoff)
    return [a - b for a, b in zip(x, lp)]


def reverb(x, wet=0.25, room=0.82, tail=1.2):
    """Small Schroeder reverb: 4 parallel combs + 2 allpasses."""
    x = x + [0.0] * int(tail * SR)
    combs = [1557, 1617, 1491, 1422]
    acc = [0.0] * len(x)
    for d in combs:
        buf = [0.0] * d
        lp, idx = 0.0, 0
        for i, v in enumerate(x):
            out = buf[idx]
            lp = out * 0.7 + lp * 0.3
            buf[idx] = v + lp * room
            idx = (idx + 1) % d
            acc[i] += out
    for d in (225, 556):
        buf = [0.0] * d
        idx = 0
        for i, v in enumerate(acc):
            b = buf[idx]
            out = -v + b
            buf[idx] = v + b * 0.5
            idx = (idx + 1) % d
            acc[i] = out
    return [d + w * wet * 0.25 for d, w in zip(x, acc)]


def write_wav(path, x):
    x = fade_out(normalize(x))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in x))


# ---------------------------------------------------------------- voices
def _resonators(freq, dur, ratios, amps, decays):
    """Sum of exponentially decaying sines via damped two-pole resonators (fast, no sin() per sample)."""
    n = int(dur * SR)
    out = [0.0] * n
    for r, a, d in zip(ratios, amps, decays):
        f = freq * r
        if f >= SR / 2.2:
            continue
        w = 2 * math.pi * f / SR
        rr = math.exp(-1 / (d * SR))
        c1, c2 = 2 * rr * math.cos(w), -rr * rr
        y1, y2 = a * math.sin(w), 0.0
        for i in range(n):
            out[i] += y1
            y1, y2 = c1 * y1 + c2 * y2, y1
    return out


def bell(freq, dur=1.6, bright=1.0):
    ratios = [0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166, 5.433]
    amps = [.35, 1, .6, .4, .7 * bright, .3 * bright, .25, .2 * bright, .12 * bright, .08 * bright]
    decays = [dur * .9, dur * .6, dur * .45, dur * .35, dur * .3, dur * .2, dur * .18, dur * .15, dur * .1, dur * .07]
    x = _resonators(freq, dur, ratios, amps, decays)
    for i in range(min(len(x), 60)):
        x[i] *= i / 60
    return x


def metal(freq, dur=0.6, ring=1.0):
    """Struck bar / anvil: inharmonic free-bar modes, fast decay."""
    return _resonators(freq, dur, [1, 2.756, 5.404, 8.933], [1, .6, .35, .2],
                       [dur * .5 * ring, dur * .3 * ring, dur * .15, dur * .08])


def gong(freq, dur=2.2):
    ratios = [1, 1.52, 2.27, 2.89, 3.75, 4.6, 5.9]
    return _resonators(freq, dur, ratios, [1, .8, .6, .45, .3, .2, .1],
                       [dur * .7, dur * .55, dur * .45, dur * .35, dur * .25, dur * .18, dur * .12])


def horn(freq, dur, end_freq=None, bright=1.0, attack=0.06, vibrato=4.5, grit=0.0):
    """Brass voice: band-limited harmonics, brightness follows the envelope, optional glide and growl."""
    n = int(dur * SR)
    end_freq = end_freq or freq
    phase, out = 0.0, []
    rng = random.Random(int(freq))
    for i in range(n):
        t = i / SR
        env = min(1, t / attack) * min(1, (dur - t) / 0.12)
        f = freq * (end_freq / freq) ** (t / dur) * (1 + 0.006 * math.sin(2 * math.pi * vibrato * t) * min(1, t / .25))
        phase += 2 * math.pi * f / SR
        harm = max(2, int((3 + 9 * env * bright)))
        s = 0.0
        for h in range(1, harm + 1):
            if f * h > 9000:
                break
            s += math.sin(phase * h) / h ** 1.15
        if grit:
            s += grit * (rng.random() - .5) * env
        out.append(s * env)
    return saturate(out, 1 + 3 * grit) if grit else out


def drum(freq=70, dur=0.6, punch=2.5, noise=0.35, seed=1):
    n = int(dur * SR)
    rng = random.Random(seed)
    phase, out = 0.0, []
    for i in range(n):
        t = i / SR
        f = freq * (1 + punch * math.exp(-t * 35))
        phase += 2 * math.pi * f / SR
        body = math.sin(phase) * math.exp(-t * 6 / dur)
        hit = (rng.random() * 2 - 1) * math.exp(-t * 60) * noise
        out.append(body + hit)
    return lowpass(out, 2500)


def noise(dur, seed=3, env=None):
    rng = random.Random(seed)
    n = int(dur * SR)
    return [(rng.random() * 2 - 1) * (env(i / SR) if env else 1) for i in range(n)]


def shing(dur=0.7, rising=True, low=False):
    """Blade drawn from a scabbard: bright filtered scrape + ringing steel."""
    scrape = noise(dur, 9, lambda t: math.sin(math.pi * min(1, t / dur * 1.3)) ** 2)
    scrape = highpass(scrape, 1800 if low else 3500)
    f0, f1 = (1500, 3100) if rising else (3100, 1500)
    if low:
        f0, f1 = f0 * .6, f1 * .6
    ring = metal(f1, dur + .6, ring=2.5)
    start = dur * .7 if rising else 0.05
    return reverb(mix(start + dur + .6, (0, scrape, .5), (start, ring, .5)), .2, tail=.6)


def sparkle(root, steps, gap=0.06, dur=0.9):
    total = gap * len(steps) + dur
    return mix(total, *[(i * gap, bell(root * 2 ** (s / 12), dur, .6), .6) for i, s in enumerate(steps)])


def crackle(dur, density=90, seed=5):
    rng = random.Random(seed)
    out = [0.0] * int(dur * SR)
    for _ in range(int(dur * density)):
        p = rng.randrange(len(out) - 200)
        a = rng.uniform(.3, 1)
        for i in range(rng.randint(20, 160)):
            out[p + i] += a * (rng.random() * 2 - 1) * math.exp(-i / 30)
    return highpass(out, 900)


def rustle(dur=0.6):
    rng = random.Random(4)
    bursts = [rng.uniform(.5, 1) if rng.random() < .3 else .15 for _ in range(int(dur * 40) + 1)]
    x = noise(dur, 11, lambda t: bursts[int(t * 40)] * math.sin(math.pi * t / dur))
    return lowpass(highpass(x, 1200), 6000)


# ---------------------------------------------------------------- event sets
def _n(root, semis):
    return root * 2 ** (semis / 12)


def crown(root):
    n = lambda s: _n(root, s)
    rv = reverb
    return {
        "bell": rv(mix(1.6, (0, bell(n(12), 1.4), 1))),
        "dialog-information": rv(mix(1.8, (0, bell(n(7), 1.4), 1), (.12, bell(n(12), 1.4), .8))),
        "dialog-question": rv(mix(1.8, (0, bell(n(7), 1.4), .9), (.16, bell(n(14), 1.4), .9))),
        "dialog-warning": rv(mix(1.9, (0, bell(n(12), 1.4), 1), (.2, bell(n(7), 1.5), 1), (0, metal(n(24), .2), .2))),
        "dialog-error": rv(mix(1.6, (0, metal(220, 1.2), 1), (0, metal(233, 1.2), .7), (0, drum(90, .4), .9)), .3),
        "message": rv(mix(1.6, (0, bell(n(12), 1.2, .7), 1), (.1, bell(n(16), 1.2, .7), .7))),
        "message-new-instant": rv(sparkle(n(12), [0, 4, 7, 12])),
        "complete": rv(mix(1.4, (0, horn(n(-12), .18), .8), (.2, horn(n(-5), .18), .8), (.4, horn(n(0), .7), 1)), .35),
        "desktop-login": rv(mix(2.9, (0, horn(n(-12), .35), .8), (.42, horn(n(-5), .35), .8),
                                (.84, horn(n(0), 1.4), 1), (.84, bell(n(12), 2.0), .55), (1.05, bell(n(19), 1.8), .4)), .4, tail=1.8),
        "desktop-logout": rv(mix(2.4, (0, horn(n(0), .35), .9), (.42, horn(n(-5), .35), .8), (.84, horn(n(-12), 1.2), .9)), .4),
        "device-added": shing(.6, True),
        "device-removed": shing(.5, False),
        "power-plug": rv(sparkle(n(12), [0, 4, 7, 12, 16], .05)),
        "power-unplug": rv(sparkle(n(12), [16, 12, 7, 4, 0], .05)),
        "battery-low": rv(mix(1.9, (0, bell(n(-5), 1.2), 1), (.5, bell(n(-5), 1.2), 1))),
        "trash-empty": mix(1.0, (0, rustle(.6), .6), (.5, drum(110, .35, 1.5, .2), .8)),
        "audio-volume-change": mix(.25, (0, metal(n(24), .2), 1)),
        "screen-capture": mix(.45, (0, metal(1900, .15), 1), (.07, metal(1300, .3), .8), (0, noise(.04, 2), .4)),
        "window-attention": rv(mix(1.5, (0, bell(n(19), 1.2), 1))),
    }


def ember(root):
    n = lambda s: _n(root, s)
    rv = reverb
    war = lambda f, d, e=None: horn(f, d, e, bright=.8, attack=.12, vibrato=3.5, grit=.35)
    return {
        "bell": rv(mix(1.4, (0, metal(n(24), .9, 2), 1), (0, drum(80, .3), .4))),
        "dialog-information": rv(mix(2.2, (0, gong(n(12), 2.0), 1), (0, drum(70, .4), .5))),
        "dialog-question": rv(mix(2.2, (0, gong(n(12), 1.6), .9), (.18, gong(n(15), 1.8), .8))),
        "dialog-warning": rv(mix(1.4, (0, drum(65, .5, seed=1), 1), (.22, drum(65, .5, seed=2), 1))),
        "dialog-error": rv(mix(1.6, (0, drum(55, .7), 1), (0, war(n(-12), .8, n(-13)), .7)), .3),
        "message": rv(mix(1.4, (0, metal(n(19), .8, 2), 1), (.09, metal(n(24), .8, 2), .7))),
        "message-new-instant": rv(mix(1.0, (0, crackle(.35), .5), (.05, metal(n(24), .5, 2), .6), (.12, metal(n(31), .5, 2), .5))),
        "complete": rv(mix(1.6, (0, drum(70, .4), .9), (.1, war(n(-12), 1.2, n(-5)), .9)), .35),
        "desktop-login": rv(mix(3.2, (0, drum(60, .5, seed=1), 1), (.3, drum(60, .5, seed=2), .9), (.6, drum(60, .6, seed=3), 1),
                                (.75, war(n(-12), 1.0), .9), (1.75, war(n(-5), 1.1, n(-7)), .9), (.6, crackle(2.2), .25)), .4, tail=1.8),
        "desktop-logout": rv(mix(2.4, (0, war(n(-5), 1.4, n(-12)), .9), (1.2, drum(55, .8), 1)), .4),
        "device-added": shing(.6, True, low=True),
        "device-removed": shing(.5, False, low=True),
        "power-plug": mix(1.0, (0, highpass(noise(.6, 6, lambda t: t / .6), 600), .5), (.45, crackle(.5), .6), (.5, drum(80, .3), .5)),
        "power-unplug": mix(1.0, (0, highpass(noise(.6, 7, lambda t: 1 - t / .6), 600), .5), (.5, drum(60, .4), .6)),
        "battery-low": mix(1.4, (0, drum(55, .3, seed=1), 1), (.18, drum(50, .3, seed=2), .8),
                           (.7, drum(55, .3, seed=3), 1), (.88, drum(50, .3, seed=4), .8)),
        "trash-empty": mix(1.2, (0, crackle(.9, 140), .7), (.05, drum(90, .4, 1.5, .3), .7)),
        "audio-volume-change": mix(.25, (0, metal(n(19), .2), 1)),
        "screen-capture": mix(.5, (0, metal(900, .2), 1), (.09, metal(700, .3), .9), (.18, metal(800, .2), .6)),
        "window-attention": rv(mix(2.0, (0, gong(n(19), 1.8), 1))),
    }


def whisper(dur, seed=13, rising=None):
    """Breathy, formant-ish noise: band-limited noise with a slow swell."""
    def env(t):
        x = t / dur
        if rising is True:
            return x ** 1.5
        if rising is False:
            return (1 - x) ** 1.5
        return math.sin(math.pi * x) ** 2
    return lowpass(highpass(noise(dur, seed, env), 700), 3200)


def rattle(dur=0.5, hits=9, seed=17):
    """Clattering bones: a burst of short, dry, woody knocks."""
    rng = random.Random(seed)
    parts = [(rng.uniform(0, dur * .8), metal(rng.uniform(700, 1400), .09, .4), rng.uniform(.4, 1)) for _ in range(hits)]
    return mix(dur + .15, *parts)


def grave(root):
    n = lambda s: _n(root, s)
    rv = lambda x, wet=.45, tail=1.8: reverb(x, wet, .88, tail)
    ghost = lambda f, d, e=None: horn(f, d, e, bright=.25, attack=.35, vibrato=5.5)
    toll = lambda f, d=2.6: bell(f, d, .45)
    return {
        "bell": rv(mix(2.6, (0, toll(n(12)), 1))),
        "dialog-information": rv(mix(2.8, (0, toll(n(12)), 1), (.02, toll(n(13), 2.2), .25))),
        "dialog-question": rv(mix(3.0, (0, toll(n(12)), .9), (.25, toll(n(18)), .7))),
        "dialog-warning": rv(mix(3.2, (0, toll(n(0)), 1), (.55, toll(n(0)), .9))),
        "dialog-error": rv(mix(3.0, (0, gong(n(-12), 2.4), 1), (0, whisper(1.2), .5), (0, drum(50, .6), .7))),
        "message": rv(sparkle(n(12), [0, 3, 6], .09, 1.2)),
        "message-new-instant": rv(sparkle(n(12), [0, 3, 6, 9], .06, 1.0)),
        "complete": rv(mix(2.8, (0, ghost(n(-12), 1.6, n(-9)), .8), (.4, toll(n(12)), .6))),
        "desktop-login": rv(mix(5.0, (0, toll(n(0), 3.2), 1), (.9, toll(n(0), 3.2), .9), (1.8, toll(n(-5), 3.4), 1),
                                (.3, ghost(n(-12), 3.4, n(-11)), .45), (.3, ghost(n(-5), 3.4, n(-4)), .3),
                                (0, whisper(2.5, 21), .35)), .5, 2.2),
        "desktop-logout": rv(mix(3.8, (0, ghost(n(-5), 2.4, n(-17)), .7), (0, toll(n(-5), 3.0), .9), (.2, whisper(1.6, 22, False), .4)), .5),
        "device-added": shing(.6, True, low=True),
        "device-removed": shing(.5, False, low=True),
        "power-plug": rv(mix(1.6, (0, whisper(1.0, 23, True), .8), (.85, toll(n(19), 1.0), .4))),
        "power-unplug": rv(mix(1.6, (0, whisper(1.0, 24, False), .8))),
        "battery-low": rv(mix(2.2, (0, drum(48, .5, seed=1), 1), (.24, drum(44, .5, seed=2), .8),
                              (1.0, drum(48, .5, seed=3), 1), (1.24, drum(44, .5, seed=4), .8)), .3),
        "trash-empty": rv(rattle(.7, 12), .25, 1.0),
        "audio-volume-change": mix(.25, (0, metal(1050, .12, .5), 1)),
        "screen-capture": mix(.5, (0, rattle(.25, 4, 31), 1)),
        "window-attention": rv(mix(2.6, (0, toll(n(19)), 1))),
    }


STYLES = {"crown": crown, "ember": ember, "grave": grave}

# freedesktop event -> extra names that should play the same file
SOUND_ALIASES = {
    "bell": ["bell-terminal", "bell-window-system"],
    "dialog-information": ["dialog-information-severe"],
    "dialog-error": ["suspend-error", "power-unplug-battery-low"],
    "message": ["message-new-email"],
    "complete": ["software-update-available", "outcome-success"],
    "desktop-login": ["service-login", "system-ready"],
    "desktop-logout": ["service-logout", "system-shutdown"],
    "device-added": ["device-added-media", "network-connectivity-established"],
    "device-removed": ["device-removed-media", "network-connectivity-lost"],
    "battery-low": ["battery-caution"],
    "screen-capture": ["camera-shutter"],
}

# Windows AppEvents (app\event) -> our sound
WINDOWS_SOUNDS = {
    r".Default\.Default": "bell",
    r".Default\SystemAsterisk": "dialog-information",
    r".Default\SystemExclamation": "dialog-warning",
    r".Default\SystemHand": "dialog-error",
    r".Default\SystemQuestion": "dialog-question",
    r".Default\SystemNotification": "message",
    r".Default\Notification.Default": "message",
    r".Default\Notification.IM": "message-new-instant",
    r".Default\Notification.Mail": "message",
    r".Default\Notification.Reminder": "window-attention",
    r".Default\MailBeep": "message",
    r".Default\DeviceConnect": "device-added",
    r".Default\DeviceDisconnect": "device-removed",
    r".Default\DeviceFail": "dialog-error",
    r".Default\LowBatteryAlarm": "battery-low",
    r".Default\CriticalBatteryAlarm": "battery-low",
    r".Default\WindowsUAC": "dialog-question",
    r".Default\WindowsLogon": "desktop-login",
    r".Default\WindowsLogoff": "desktop-logout",
    r".Default\SystemExit": "desktop-logout",
    r"Explorer\EmptyRecycleBin": "trash-empty",
}
