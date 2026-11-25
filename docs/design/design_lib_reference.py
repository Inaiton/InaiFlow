import os, json
OUT = '/mnt/user-data/outputs/artifacts/698de1bf/project'
LOGO = '/_blob/2c3b8a1d13dbdca9534c80586fe447f6'
LOGO_DARK = '/_blob/cb13e8469c451feed9dc6c3adc80367b'
FONT = "'Google Sans Flex','Google Sans',Inter,system-ui,sans-serif"

T = {  # tone: (tint, text, solid)
 'success': ('#ECFDF3', '#067647', '#12B76A'),
 'warning': ('#FFFAEB', '#B54708', '#F79009'),
 'danger':  ('#FEF3F2', '#B42318', '#F04438'),
 'indigo':  ('#EEF2FF', '#3538CD', '#4F46E5'),
 'sky':     ('#F0F9FF', '#026AA2', '#0BA5EC'),
 'violet':  ('#F4F3FF', '#5925DC', '#7A5AF8'),
 'teal':    ('#F0FDF9', '#107569', '#0E9384'),
 'accent':  ('#FBEFEC', '#A6452F', '#C35E49'),
 'orange':  ('#FEF6EE', '#B93815', '#EF6820'),
 'gray':    ('#F2F4F7', '#344054', '#667085'),
}

I = {
 'wallet': 'M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4',
 'dash': 'M4 3h5a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM15 3h5a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM15 12h5a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1zM4 16h5a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1z',
 'file': 'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7ZM14 2v4a2 2 0 0 0 2 2h4M16 13H8M16 17H8M10 9H8',
 'book': 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2zM22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z',
 'bank': 'M3 22h18M6 18v-7M10 18v-7M14 18v-7M18 18v-7M12 2 20 7H4z',
 'users': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8a4 4 0 1 0 0-8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
 'receipt': 'M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1ZM16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 17.5v-11',
 'chart': 'M3 3v18h18M18 17V9M13 17V5M8 17v-3',
 'wrench': 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z',
 'flow': 'M5 3h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM7 11v4a2 2 0 0 0 2 2h4M15 13h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2z',
 'folder': 'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
 'org': 'M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18ZM6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2M10 6h4M10 10h4M10 14h4M10 18h4',
 'box': 'M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16ZM3.3 7l8.7 5 8.7-5M12 22V12',
 'play': 'M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20M10 8l6 4-6 4z',
 'shield': 'M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1zM9 12l2 2 4-4',
 'scan': 'M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10',
 'edit': 'M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z',
 'layers': 'M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
 'id': 'M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM9 8a2 2 0 1 0 0 4a2 2 0 1 0 0-4M15 9h3M15 13h3M6 16c.8-1.5 2-2 3-2s2.2.5 3 2',
 'lock': 'M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2zM7 11V7a5 5 0 0 1 10 0v4',
 'history': 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8M3 3v5h5M12 7v5l4 2',
 'card': 'M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zM2 10h20',
 'search': 'M11 3a8 8 0 1 0 0 16a8 8 0 1 0 0-16M21 21l-4.3-4.3',
 'plus': 'M5 12h14M12 5v14',
 'down': 'm6 9 6 6 6-6', 'right': 'm9 18 6-6-6-6', 'none': '',
 'updown': 'm7 15 5 5 5-5M7 9l5-5 5 5',
 'home': 'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z',
 'mail': 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM22 6l-10 7L2 6',
 'sliders': 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
 'globe': 'M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
 'truck': 'M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2M15 18H9M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14M7 16a2 2 0 1 0 0 4a2 2 0 1 0 0-4M17 16a2 2 0 1 0 0 4a2 2 0 1 0 0-4',
 'arrow': 'M5 12h14m-7-7 7 7-7 7',
 'dl': 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
 'upload': 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12',
 'check': 'M20 6 9 17l-5-5',
 'checkc': 'M22 11.08V12a10 10 0 1 1-5.93-9.14M9 11l3 3L22 4',
 'x': 'M18 6 6 18M6 6l12 12',
 'alert': 'm21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3M12 9v4M12 17h.01',
 'clock': 'M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20M12 6v6l4 2',
 'filter': 'M22 3H2l8 9.46V19l4 2v-8.54z',
 'cal': 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM16 2v4M8 2v4M3 10h18',
 'paper': 'M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48',
 'eye': 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7ZM12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6',
 'more': 'M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2M19 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2M5 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2',
 'trend': 'M22 7 13.5 15.5 8.5 10.5 2 17M16 7h6v6',
 'in': 'M17 7 7 17M17 17H7V7', 'out': 'M7 7h10v10M7 17 17 7',
 'gauge': 'M12 14l4-4M3.34 19a10 10 0 1 1 17.32 0',
 'copy': 'M10 8h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2zM4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2',
 'link': 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71',
 'camera': 'M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3zM12 10a3 3 0 1 0 0 6a3 3 0 1 0 0-6',
 'zap': 'M13 2 3 14h9l-1 8 10-12h-9l1-8z',
 'phone': 'M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2',
 'help': 'M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01',
 'bell': 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0',
 'key': 'M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4zM16.5 6.5a.5.5 0 1 0 0 1 .5.5 0 1 0 0-1',
}

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def icon(name, size=16, color='#667085', sw=1.75):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{I[name]}"></path></svg>')

def chip(t, tone='gray', size=11.5):
    a, b, _ = T[tone]
    return f'<span style="padding: 2px 7px; border-radius: 6px; background: {a}; color: {b}; font-size: {size}px; font-weight: 600; white-space: nowrap">{t}</span>'

def dot(tone, size=8):
    return f'<span style="width: {size}px; height: {size}px; border-radius: 2px; background: {T[tone][2]}; flex: none"></span>'

def kbd(t):
    return f'<kbd style="padding: 2px 6px; border-radius: 6px; background: #F2F4F7; border: 1px solid #EAECF0; font: inherit; font-size: 10.5px; font-weight: 500; color: #667085; white-space: nowrap">{t}</kbd>'

def btn(label, kind='secondary', ic=None, k=None, href=None):
    if kind == 'primary':
        st = 'background: #C35E49; color: #FFFFFF; border: 0'; ic_c = '#FFFFFF'
    elif kind == 'dark':
        st = 'background: #1D2939; color: #FFFFFF; border: 0'; ic_c = '#FFFFFF'
    elif kind == 'ghost':
        st = 'background: transparent; color: #344054; border: 0'; ic_c = '#344054'
    elif kind == 'danger':
        st = 'background: #FFFFFF; color: #B42318; border: 1px solid #FECDCA'; ic_c = '#B42318'
    else:
        st = 'background: #FFFFFF; color: #1D2939; border: 1px solid #EAECF0'; ic_c = '#344054'
    inner = (icon(ic, 16, ic_c, 2) if ic else '') + label
    if k:
        inner += f'<span style="font-size: 11px; font-weight: 500; opacity: 0.75">{k}</span>'
    base = f'display: inline-flex; align-items: center; gap: 8px; height: 40px; padding: 0 14px; border-radius: 10px; {st}; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; white-space: nowrap; box-sizing: border-box'
    if href:
        return f'<a href="{href}" style="{base}">{inner}</a>'
    return f'<button type="button" style="{base}">{inner}</button>'

def iconbtn(ic, label):
    return (f'<button type="button" aria-label="{label}" style="width: 36px; height: 36px; flex: none; border-radius: 9px; border: 1px solid #EAECF0; '
            f'background: #FFFFFF; display: inline-flex; align-items: center; justify-content: center; cursor: pointer">{icon(ic, 16, "#344054")}</button>')

def tile(ic, tone, size=36):
    a, b, _ = T[tone]
    return f'<span style="width: {size}px; height: {size}px; flex: none; border-radius: 9px; background: {a}; display: flex; align-items: center; justify-content: center">{icon(ic, int(size*0.5), b, 1.9)}</span>'

def h2(title, sub=None, right=''):
    s = f'<span style="font-size: 12.5px; color: #667085">{sub}</span>' if sub else ''
    return (f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px"><div style="flex: 1 1 200px; display: flex; flex-direction: column; gap: 3px">'
            f'<h2 style="margin: 0; font-size: 16px; font-weight: 600; color: #1D2939">{title}</h2>{s}</div>{right}</div>')

def card(body, title=None, sub=None, right='', flex='1 1 360px', gap=16, pad='18px 20px', bg='#FFFFFF', border=True):
    b = 'border: 1px solid #EAECF0; ' if border else ''
    head = h2(title, sub, right) if title else ''
    return (f'<article style="flex: {flex}; min-width: 0; background: {bg}; {b}border-radius: 16px; padding: {pad}; box-sizing: border-box; '
            f'display: flex; flex-direction: column; gap: {gap}px">{head}{body}</article>')

def row(*kids, gap=16, align='stretch'):
    return f'<section style="display: flex; flex-wrap: wrap; gap: {gap}px; align-items: {align}">{"".join(kids)}</section>'

def col(*kids, gap=16, flex='1 1 360px'):
    return f'<div style="flex: {flex}; min-width: 0; display: flex; flex-direction: column; gap: {gap}px">{"".join(kids)}</div>'

def stack(*kids, gap=8):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(kids)}</div>'

def hstack(*kids, gap=8, align='center', wrap=True, justify='flex-start'):
    w = 'flex-wrap: wrap; ' if wrap else ''
    return f'<div style="display: flex; {w}align-items: {align}; justify-content: {justify}; gap: {gap}px">{"".join(kids)}</div>'

def txt(t, size=13, w=400, c='#475467', extra=''):
    return f'<span style="font-size: {size}px; font-weight: {w}; color: {c}{"; " + extra if extra else ""}">{t}</span>'

def muted(t, size=12):
    return txt(t, size, 400, '#667085')

def strong(t, size=13):
    return txt(t, size, 600, '#1D2939')

def two(a, b):
    return f'<span style="display: flex; flex-direction: column; gap: 2px; min-width: 0">{a}{b}</span>'

def kpi(title, ic, tone, value, ch=None, ch_tone='success', caption='', href='#'):
    a, b, _ = T[tone]
    c = chip(ch, ch_tone, 11) if ch else ''
    return (f'<article style="background: #F4F4F6; border-radius: 16px; padding: 14px 14px 14px 16px; display: flex; flex-direction: column; gap: 6px; min-width: 0">'
            f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px"><span style="font-size: 13.5px; font-weight: 500; color: #1D2939">{title}</span>'
            f'<span style="width: 34px; height: 34px; flex: none; border-radius: 9px; background: {a}; display: flex; align-items: center; justify-content: center">{icon(ic, 18, b, 1.9)}</span></div>'
            f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap"><span style="font-size: 24px; font-weight: 600; letter-spacing: -0.3px; color: #141414; white-space: nowrap">{value}</span>{c}</div>'
            f'<div style="display: flex; align-items: center; justify-content: space-between; gap: 10px"><span style="font-size: 12px; color: #667085">{caption}</span>'
            f'<a href="{href}" aria-label="Open {esc(title).replace("&amp;", "and")}" style="width: 30px; height: 30px; flex: none; border-radius: 8px; background: #FFFFFF; box-shadow: 0 1px 2px rgba(16,24,40,0.06); display: flex; align-items: center; justify-content: center">{icon("arrow", 15, "#1D2939", 2)}</a></div></article>')

def kpis(*cards, minw=210):
    return f'<section aria-label="Key figures" style="display: grid; grid-template-columns: repeat(auto-fit, minmax({minw}px, 1fr)); gap: 16px">{"".join(cards)}</section>'

def table(cols, rows, minw=640, sel=None):
    th = ''
    for i, c in enumerate(cols):
        label, al = (c if isinstance(c, tuple) else (c, 'left'))
        r = 'border-radius: 8px 0 0 8px; ' if i == 0 else ('border-radius: 0 8px 8px 0; ' if i == len(cols) - 1 else '')
        th += f'<th scope="col" style="{r}padding: 8px 10px; text-align: {al}; font-weight: 600; white-space: nowrap">{label.upper()}</th>'
    body = ''
    for ri, rw in enumerate(rows):
        bg = ' background: #FBEFEC;' if sel is not None and ri == sel else ''
        tds = ''
        for i, cell in enumerate(rw):
            al = cols[i][1] if isinstance(cols[i], tuple) else 'left'
            tds += f'<td style="padding: 10px; text-align: {al}; vertical-align: middle">{cell}</td>'
        body += f'<tr style="border-bottom: 1px solid #EAECF0;{bg}">{tds}</tr>'
    return (f'<div style="overflow-x: auto"><table style="width: 100%; min-width: {minw}px; border-collapse: collapse; font-size: 13px; color: #475467">'
            f'<thead><tr style="background: #F2F4F7; font-size: 11px; letter-spacing: 0.4px; color: #667085">{th}</tr></thead><tbody>{body}</tbody></table></div>')

def tabs(items, active=0):
    out = ''
    for i, it in enumerate(items):
        on = i == active
        st = 'color: #1D2939; font-weight: 600; border-bottom: 2px solid #C35E49' if on else 'color: #667085; font-weight: 500; border-bottom: 2px solid transparent'
        out += f'<button type="button" role="tab" aria-selected="{"true" if on else "false"}" style="padding: 10px 12px; margin-bottom: -1px; border: 0; background: transparent; font: inherit; font-size: 13px; {st}; cursor: pointer; white-space: nowrap">{it}</button>'
    return f'<div role="tablist" style="display: flex; gap: 4px; border-bottom: 1px solid #EAECF0; overflow-x: auto">{out}</div>'

def seg(items, active=0):
    out = ''
    for i, it in enumerate(items):
        on = i == active
        st = 'background: #FFFFFF; box-shadow: 0 1px 3px rgba(16,24,40,0.08); color: #1D2939; font-weight: 600' if on else 'background: transparent; color: #667085; font-weight: 500'
        out += f'<button type="button" aria-pressed="{"true" if on else "false"}" style="padding: 7px 12px; border: 0; border-radius: 8px; {st}; font: inherit; font-size: 12.5px; cursor: pointer; white-space: nowrap">{it}</button>'
    return f'<div role="group" style="display: inline-flex; gap: 2px; padding: 3px; border-radius: 10px; background: #F2F4F7">{out}</div>'

def field(label, value='', flex='1 1 220px', kind='input', hint=None, ph='', suffix=None):
    if kind == 'select':
        ctl = f'<select style="height: 40px; padding: 0 10px; border: 1px solid #EAECF0; border-radius: 10px; background: #FFFFFF; font: inherit; font-size: 13px; color: #1D2939"><option>{value}</option></select>'
    elif kind == 'area':
        ctl = f'<textarea rows="3" style="padding: 10px; border: 1px solid #EAECF0; border-radius: 10px; font: inherit; font-size: 13px; color: #1D2939; resize: vertical">{value}</textarea>'
    else:
        sfx = f'<span style="padding: 0 10px; color: #667085; font-size: 12px; white-space: nowrap">{suffix}</span>' if suffix else ''
        ctl = (f'<span style="display: flex; align-items: center; height: 40px; border: 1px solid #EAECF0; border-radius: 10px; background: #FFFFFF">'
               f'<input type="text" value="{value}" placeholder="{ph}" style="flex: 1; min-width: 0; height: 38px; padding: 0 10px; border: 0; border-radius: 10px; background: transparent; font: inherit; font-size: 13px; color: #1D2939; outline: none">{sfx}</span>')
    hn = f'<span style="font-size: 11.5px; font-weight: 400; color: #667085">{hint}</span>' if hint else ''
    return f'<label style="flex: {flex}; min-width: 0; display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; font-weight: 500; color: #344054">{label}{ctl}{hn}</label>'

def fields(*f, gap=14):
    return f'<div style="display: flex; flex-wrap: wrap; gap: {gap}px">{"".join(f)}</div>'

def switch(label, sub='', on=True):
    track = '#0E9384' if on else '#D0D5DD'
    pos = 'margin-left: 18px' if on else 'margin-left: 2px'
    s = f'<span style="font-size: 12px; color: #667085">{sub}</span>' if sub else ''
    return (f'<div style="display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #F2F4F7"><span style="flex: 1; display: flex; flex-direction: column; gap: 2px">'
            f'<span style="font-size: 13px; font-weight: 600; color: #1D2939">{label}</span>{s}</span>'
            f'<button type="button" role="switch" aria-checked="{"true" if on else "false"}" aria-label="{label}" style="width: 40px; height: 24px; flex: none; border: 0; border-radius: 7px; background: {track}; padding: 0; display: flex; align-items: center; cursor: pointer">'
            f'<span style="width: 20px; height: 20px; border-radius: 5px; background: #FFFFFF; {pos}; box-shadow: 0 1px 2px rgba(16,24,40,0.2)"></span></button></div>')

def bar(pct, tone='teal', h=8):
    return f'<div style="height: {h}px; border-radius: 3px; background: #EAECF0"><div style="width: {pct}%; height: {h}px; border-radius: 3px; background: {T[tone][2]}"></div></div>'

def kv(rows):
    out = ''
    for k, v in rows:
        out += f'<div style="display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid #F2F4F7; font-size: 13px"><span style="color: #667085">{k}</span><span style="color: #1D2939; font-weight: 600; text-align: right">{v}</span></div>'
    return f'<div>{out}</div>'

def listrow(left, right='', pad='10px 12px', bg='#F9F9FB'):
    return f'<div style="display: flex; align-items: center; gap: 12px; padding: {pad}; border-radius: 12px; background: {bg}; border: 1px solid #EAECF0">{left}<span style="margin-left: auto; display: flex; align-items: center; gap: 8px">{right}</span></div>'

def avatar(initials, tone='indigo', size=32):
    return f'<span style="width: {size}px; height: {size}px; flex: none; border-radius: 9px; background: {T[tone][0]}; color: {T[tone][1]}; display: flex; align-items: center; justify-content: center; font-size: {int(size*0.38)}px; font-weight: 600">{initials}</span>'

def placeholder(label, h=200, dark=False):
    bg = '#1D2939' if dark else '#F9F9FB'
    c = '#D0D5DD' if dark else '#98A2B3'
    return (f'<div role="img" aria-label="{label}" style="height: {h}px; border-radius: 12px; background: {bg}; border: 1px dashed {"#475467" if dark else "#D0D5DD"}; '
            f'display: flex; align-items: center; justify-content: center; text-align: center; padding: 12px; box-sizing: border-box; color: {c}; font-size: 12.5px">{label}</div>')

CRUMB = {'Accounts': 'Main.dc.html', 'Vouchers': 'Acc-Voucher.dc.html', 'Day book': 'Acc-Daybook.dc.html', 'Masters': 'Acc-Ledgers.dc.html', 'Inventory': 'Acc-Inventory.dc.html',
 'Banking': 'Acc-Banking.dc.html', 'Payroll': 'Acc-Payroll.dc.html', 'Pay runs': 'Acc-Payroll.dc.html', 'Taxation': 'Acc-GST.dc.html', 'GST': 'Acc-GST.dc.html', 'Reports': 'Acc-Reports.dc.html', 'Utilities': 'Acc-Utilities.dc.html',
 'Operations': 'Ops-Dashboard.dc.html', 'Items': 'Ops-Items.dc.html', 'Workflows': 'Ops-Workflow.dc.html', 'Period runs': 'Ops-Runs.dc.html', 'ISO compliance': 'Ops-ISO.dc.html',
 'Documents': 'Doc-Explorer.dc.html', 'Explorer': 'Doc-Explorer.dc.html', 'Templates': 'Doc-Templates.dc.html', 'Report studio': 'Doc-Editor.dc.html', 'Scanner': 'Doc-Scan.dc.html',
 'Organization': 'Org-Profile.dc.html', 'Members': 'Org-Members.dc.html', 'Roles &amp; access': 'Org-Roles.dc.html', 'Security': 'Org-Security.dc.html', 'Audit log': 'Org-Audit.dc.html', 'Billing': 'Org-Billing.dc.html',
 'Personal space': 'Me-Personal.dc.html', 'Superadmin': 'SA-Dashboard.dc.html', 'Organizations': 'SA-Orgs.dc.html', 'Global config': 'SA-Config.dc.html'}

def header(crumbs, title, sub='', actions=''):
    cr = ''
    for i, c in enumerate(crumbs):
        last = i == len(crumbs) - 1
        if i:
            cr += '<span style="color: #98A2B3" aria-hidden="true">/</span>'
        cr += (f'<span style="color: #A6452F; font-weight: 500">{c}</span>' if last else f'<a href="{CRUMB.get(c, "Main.dc.html")}" style="color: #667085; text-decoration: none">{c}</a>')
    s = f'<p style="margin: 0; font-size: 13.5px; color: #667085">{sub}</p>' if sub else ''
    return (f'<section style="display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px"><div style="flex: 1 1 420px; display: flex; flex-direction: column; gap: 6px">'
            f'<nav aria-label="Breadcrumb" style="display: flex; gap: 6px; font-size: 12.5px">{cr}</nav>'
            f'<h1 style="margin: 0; font-size: 26px; font-weight: 600; color: #141414; letter-spacing: -0.2px">{title}</h1>{s}</div>'
            f'<div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center">{actions}</div></section>')

HEAD = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Google+Sans+Flex:wght@400;500;600;700&amp;display=swap" rel="stylesheet">
<style>
body{{margin:0;background:#F9F9FB}}
a{{color:#3538CD}}a:hover{{color:#2D31A6}}
</style>
</helmet>
'''

def foot(w, h, logic='return {};'):
    return ('</x-dc>\n<script type="text/x-dc" data-dc-script data-props=\'{"$preview":{"width":%d,"height":%d}}\'>\n'
            'class Component extends DCLogic {\n  renderVals() {\n    %s\n  }\n}\n</script>\n</body>\n</html>\n') % (w, h, logic)

VTYPE = {'Acc-V-Contra.dc.html': 'Contra', 'Acc-V-Payment.dc.html': 'Payment', 'Acc-V-Receipt.dc.html': 'Receipt', 'Acc-V-Journal.dc.html': 'Journal', 'Acc-V-Sales.dc.html': 'Sales',
 'Acc-Voucher.dc.html': 'Purchase', 'Acc-V-DebitNote.dc.html': 'Debit note', 'Acc-V-CreditNote.dc.html': 'Credit note', 'Acc-V-StockJournal.dc.html': 'Stock journal', 'Acc-V-MfgJournal.dc.html': 'Mfg journal', 'Acc-V-Orders.dc.html': 'Orders'}
def rbar_for(f):
    if f in VTYPE: return 'voucher', VTYPE[f]
    if f.startswith(('Acc-Rep', 'Acc-Reports', 'Acc-Daybook', 'Acc-Tax', 'Acc-GST', 'Acc-Utilities')): return 'report', ''
    if f.startswith(('Acc-M-', 'Acc-I-', 'Acc-Ledgers', 'Acc-Inventory')): return 'master', ''
    return 'default', ''
PAGES = []  # (file, title, page_id, h)

def write(fname, html):
    with open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
        f.write(html)

def page(fname, title, module, active, head_html, body_html, h=1100, pid='accounts', personal=False):
    root = f"min-height: 100vh; background: #F9F9FB; display: flex; flex-wrap: wrap; align-items: stretch; font-family: {FONT}; color: #1D2939; font-size: 13px"
    tb = '<dc-import name="Topbar" personal="yes" hint-size="100%,68px"></dc-import>' if personal else '<dc-import name="Topbar" hint-size="100%,68px"></dc-import>'
    if module == 'accounts':
        tb += '\n<dc-import name="AccBar" hint-size="100%,40px"></dc-import>'
        rset, ract = rbar_for(fname)
        head_html = (f'<div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start"><div style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 20px">{head_html}\n{body_html}</div>'
                     f'<aside aria-label="Function keys" style="flex: 0 0 150px"><dc-import name="RBar" set="{rset}" active="{ract}" hint-size="150px,640px"></dc-import></aside></div>')
        body_html = ''
    html = HEAD.format(title=f'InaiFlow · {title}') + (
        f'<div style="{root}">\n'
        f'<aside aria-label="Primary navigation" style="flex: 1 1 236px; max-width: 260px; min-width: 220px; display: flex; flex-direction: column">'
        f'<dc-import module="{module}" active="{active}" name="Sidebar" hint-size="240px,1000px"></dc-import></aside>\n'
        f'<main style="flex: 999 1 560px; min-width: 0; background: #FFFFFF; border-left: 1px solid #EAECF0; box-sizing: border-box; padding: 20px 32px 28px; display: flex; flex-direction: column; gap: 20px">\n'
        f'{tb}\n{head_html}\n{body_html}\n</main>\n</div>\n') + foot(1440, h)
    write(fname, html)
    PAGES.append((fname, title, pid, h))

def bare(fname, title, body_html, h=900, pid='onboarding', w=1440):
    root = f"min-height: 100vh; background: #F9F9FB; font-family: {FONT}; color: #1D2939; font-size: 13px"
    html = HEAD.format(title=f'InaiFlow · {title}') + f'<div style="{root}">\n{body_html}\n</div>\n' + foot(w, h)
    write(fname, html)
    PAGES.append((fname, title, pid, h))

def logo_mark(size=40, dark=False):
    src = LOGO_DARK if dark else LOGO
    wc = '#FFFFFF' if dark else '#141414'
    return (f'<span style="display: flex; align-items: center; gap: 10px"><img src="{src}" alt="" style="width: {size}px; height: {size}px; object-fit: contain">'
            f'<span style="display: flex; flex-direction: column; gap: 3px"><span style="font-size: {int(size*0.62)}px; font-weight: 700; letter-spacing: -0.3px; line-height: 1; color: {wc}">Inai<span style="color: #C35E49">Flow</span></span>'
            f'<span style="display: flex; gap: 3px"><span style="width: 22px; height: 2px; background: #C35E49; border-radius: 1px"></span><span style="flex: 1; height: 2px; background: {wc}; border-radius: 1px"></span></span></span></span>')

def tok(v):
    return f'<span>{{</span><span>{{</span>{v}<span>}}</span><span>}}</span>'


def link(text, href='#', color='#3538CD'):
    return f'<a href="{href}" style="display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; color: {color}; text-decoration: none">{text}{icon("arrow", 14, color, 2)}</a>'

def _panel(title, sub, body, footer, close, w, drawer):
    s = f'<span style="font-size: 12.5px; color: #667085">{sub}</span>' if sub else ''
    shape = (f'width: 100%; max-width: {w}px; height: 100%; border-radius: 16px 0 0 16px' if drawer else
             f'width: 100%; max-width: {w}px; max-height: 100%; border-radius: 16px')
    ft = f'<div style="padding: 14px 20px; border-top: 1px solid #EAECF0; display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px">{footer}</div>' if footer else ''
    return (f'<div role="dialog" aria-modal="true" aria-label="{esc(title)}" style="{shape}; box-sizing: border-box; background: #FFFFFF; box-shadow: 0 24px 48px rgba(16,24,40,0.18); display: flex; flex-direction: column; overflow: hidden">'
            f'<div style="padding: 18px 20px; border-bottom: 1px solid #EAECF0; display: flex; align-items: flex-start; gap: 12px"><div style="flex: 1; display: flex; flex-direction: column; gap: 3px">'
            f'<h2 style="margin: 0; font-size: 17px; font-weight: 600; color: #141414">{title}</h2>{s}</div>'
            f'<a href="{close}" aria-label="Close" style="width: 32px; height: 32px; flex: none; border-radius: 8px; border: 1px solid #EAECF0; display: flex; align-items: center; justify-content: center">{icon("x", 16, "#344054", 2)}</a></div>'
            f'<div style="padding: 20px; overflow: auto; flex: 1; display: flex; flex-direction: column; gap: 16px">{body}</div>{ft}</div>')

def modal(title, sub, body, footer='', close='#', w=640):
    return _panel(title, sub, body, footer, close, w, False)

def drawer(title, sub, body, footer='', close='#', w=480):
    return _panel(title, sub, body, footer, close, w, True)

def overlay_page(fname, title, parent, parent_h, panel_html, pid, kind='modal'):
    """Full page = the real parent page (dc-import) dimmed, with a modal or drawer on top.
    parent: parent file name, e.g. 'Acc-Voucher.dc.html'. The close link of the panel should point back to parent."""
    stem = parent.replace('.dc.html', '')
    pos = ('justify-content: flex-end; align-items: stretch; padding: 0' if kind == 'drawer' else 'justify-content: center; align-items: flex-start; padding: 72px 24px 24px')
    root = f"position: relative; min-height: 100vh; font-family: {FONT}; color: #1D2939; font-size: 13px; background: #F9F9FB"
    html = HEAD.format(title=f'InaiFlow · {title}') + (
        f'<div style="{root}">\n<dc-import name="{stem}" hint-size="100%,{parent_h}px"></dc-import>\n'
        f'<div style="position: absolute; inset: 0; background: rgba(16,24,40,0.45); display: flex; {pos}; box-sizing: border-box">{panel_html}</div>\n</div>\n') + foot(1440, parent_h)
    write(fname, html)
    PAGES.append((fname, title, pid, parent_h))

def step_policy():
    return (h2('Execution options', 'For owners who don’t record every reading') +
            stack(switch('Allow skip on command', 'Step marked Skipped with reason · Full control or step owner', True),
                  switch('Allow mark success on command', 'All input units passed as accepted · logged in audit trail', True),
                  switch('Quick QC · count only', 'Enter accepted / rejected totals; observed readings auto-fill with the nominal value', True), gap=0) +
            fields(field('Default observed value', 'Nominal from spec (40.00 mm)', '1 1 220px', 'select', hint='Used when a reading is left blank'),
                   field('Label on reports', 'Auto · nominal', '1 1 160px')))

def auto_readings(n=5, nom='40.00', od='80.00'):
    return table(['#', ('Bore mm', 'right'), ('OD mm', 'right'), 'Source'], [[str(i), nom, od, chip('Auto · nominal', 'sky', 11)] for i in range(1, n + 1)], minw=300)

def qc_mode(quick=True):
    return (seg(['Quick · count only', 'Full readings'], 0 if quick else 1) +
            f'<div style="padding: 10px 12px; border-radius: 10px; background: #F0F9FF; border: 1px solid #B9E6FE; font-size: 12.5px; color: #026AA2">'
            f'<b>Quick QC on</b> · only totals are needed. Blank readings are filled with the nominal value from the spec and tagged “Auto · nominal” on the dossier and reports.</div>')

# ---------- calm / guided building blocks ----------
def guide(steps, current=0, compact=False):
    """Numbered stepper. steps: list of (title, helper[, href])."""
    out = ''
    for i, s in enumerate(steps):
        t, hlp = s[0], s[1]; href = s[2] if len(s) > 2 else None
        done, on = i < current, i == current
        bg = '#12B76A' if done else ('#C35E49' if on else '#FFFFFF')
        fc = '#FFFFFF' if (done or on) else '#98A2B3'
        bd = 'transparent' if (done or on) else '#D0D5DD'
        num = icon('check', 14, '#FFFFFF', 2.6) if done else str(i + 1)
        helper = '' if compact else f'<span style="font-size: 12px; color: #667085">{hlp}</span>'
        inner = (f'<span style="width: 28px; height: 28px; flex: none; border-radius: 8px; background: {bg}; border: 1.5px solid {bd}; box-sizing: border-box; color: {fc}; font-size: 13px; font-weight: 700; display: flex; align-items: center; justify-content: center">{num}</span>'
                 f'<span style="display: flex; flex-direction: column; gap: 2px; min-width: 0"><span style="font-size: 13.5px; font-weight: {700 if on else 600}; color: {"#141414" if on else ("#344054" if done else "#667085")}">{t}</span>{helper}</span>')
        tag = f'<a href="{href}" style="text-decoration: none; ' if href else '<div style="'
        end = '</a>' if href else '</div>'
        out += f'{tag}flex: 1 1 180px; display: flex; align-items: flex-start; gap: 10px; padding: 12px; border-radius: 12px; background: {"#FFFBFA" if on else "transparent"}; border: 1px solid {"#F4C7BC" if on else "transparent"}">{inner}{end}'
        if i < len(steps) - 1:
            out += f'<span aria-hidden="true" style="flex: 0 0 24px; height: 2px; margin-top: 25px; background: {"#12B76A" if done else "#EAECF0"}"></span>'
    return f'<nav aria-label="Steps" style="display: flex; flex-wrap: wrap; align-items: flex-start; gap: 0">{out}</nav>'

def hint(text, title=None, tone='sky'):
    a, b, _ = T[tone]
    t = f'<b>{title}</b> · ' if title else ''
    return (f'<div style="display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 10px; background: {a}; font-size: 12.5px; line-height: 1.5; color: {b}">'
            f'<span style="flex: none; margin-top: 1px">{icon("help", 16, b, 2)}</span><span>{t}{text}</span></div>')

def section(title, body, sub=None, right='', gap=14):
    """Borderless group: whitespace instead of boxes."""
    return f'<section style="display: flex; flex-direction: column; gap: {gap}px">{h2(title, sub, right)}{body}</section>'

def spotlight(title, sub, action_html, ic='alert', tone='accent'):
    a, b, c = T[tone]
    return (f'<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 14px; padding: 16px 18px; border-radius: 16px; background: {a}; border: 1px solid {c}33">'
            f'<span style="width: 40px; height: 40px; flex: none; border-radius: 10px; background: #FFFFFF; display: flex; align-items: center; justify-content: center">{icon(ic, 20, c, 2)}</span>'
            f'<span style="flex: 1 1 260px; display: flex; flex-direction: column; gap: 2px"><span style="font-size: 15px; font-weight: 700; color: #141414">{title}</span><span style="font-size: 12.5px; color: #475467">{sub}</span></span>{action_html}</div>')

def bigaction(ic, title, sub, href, tone='indigo'):
    a, b, _ = T[tone]
    return (f'<a href="{href}" style="flex: 1 1 200px; display: flex; align-items: center; gap: 12px; padding: 16px; border-radius: 14px; border: 1px solid #EAECF0; background: #FFFFFF; text-decoration: none">'
            f'<span style="width: 40px; height: 40px; flex: none; border-radius: 10px; background: {a}; display: flex; align-items: center; justify-content: center">{icon(ic, 20, b, 2)}</span>'
            f'<span style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 14px; font-weight: 600; color: #141414">{title}</span><span style="font-size: 12px; color: #667085">{sub}</span></span></a>')
