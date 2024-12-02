from fasthtml.common import *
import httpx
import os
from urllib.parse import parse_qs

app, rt = fast_app()


@timed_cache(
    seconds=900
)  # 15min cache (based on this page: https://fastcore.fast.ai/xtras.html#time_policy)
def fetch_leaderboard():
    url = 'https://adventofcode.com/2024/leaderboard/private/view/3297706.json'
    r = httpx.get(url, cookies={'session': os.environ['AOC_SESSION']})
    return r.json()


def format_time(seconds):
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02d}"


def get_duration(x):
    return x['duration']


def get_day_completion_times(data, day_num):
    completion_times = []
    for member in data['members'].values():
        if not member.get('name'):
            continue  # Some names are empty, so skip those
        completions = member.get('completion_day_level',
                                 {}).get(str(day_num), {})
        if '2' in completions:  # Only include members who completed part 1 and 2
            p1_time = completions['1']['get_star_ts']
            p2_time = completions['2']['get_star_ts']
            completion_times.append({
                'name': member['name'],
                'duration': p2_time - p1_time,
                'points': member.get('local_score',
                                     0)  # Default to 0 if no score yet
            })
    return sorted(completion_times, key=get_duration)


def calculate_custom_points(data):
    custom_points = {}
    for day_num in range(1, 26):  # Because 25 days of AoC
        times = get_day_completion_times(data, day_num)
        n = len(times)
        for i, entry in enumerate(times):
            if entry['name'] not in custom_points:
                custom_points[entry['name']] = 0
            custom_points[entry[
                'name']] += n - i  # Custom points based on AoC ranking system (but for SIWC)
    return custom_points


@rt('/')
def get(request):
    data = fetch_leaderboard()

    query_params = parse_qs(request.scope['query_string'].decode())
    sort_key = query_params.get('sort', ['local'])[0]
    sort_order = query_params.get('order', ['desc'])[0]

    # Get days and sort them
    days = sorted({
        int(day)
        for member in data['members'].values()
        for day in member.get('completion_day_level', {}).keys()
    })

    # Each day is a clickable link
    day_links = [
        A(f"Day {day}", href=f"/day/{day}", cls="day-link") for day in days
    ]

    # Create sorted list of members and their points
    total_points = sorted([{
        'name': m['name'],
        'points': m.get('local_score', 0)
    } for m in data['members'].values() if m.get('name')],
                          key=lambda x: x['points'],
                          reverse=True)

    custom_points = calculate_custom_points(data)

    # Add custom points to total_points
    for entry in total_points:
        entry['custom_points'] = custom_points.get(entry['name'], 0)

    if sort_key == 'local':
        total_points = sorted(total_points,
                              key=lambda x: x['points'],
                              reverse=(sort_order == 'desc'))
    elif sort_key == 'custom':
        total_points = sorted(total_points,
                              key=lambda x: x['custom_points'],
                              reverse=(sort_order == 'desc'))

    # Toggle sort order depending on next click
    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'
    order_arrow = '↓' if sort_order == 'desc' else '↑'

    header_row = Div(Grid(
        Div("Rank"),
        Div("Name"),
        Div(
            A(f"Local Score {order_arrow if sort_key == 'local' else ''}",
              href=f"?sort=local&order={next_sort_order}",
              cls="sortable-header")),
        Div(
            A(f"SIWC Score {order_arrow if sort_key == 'custom' else ''}",
              href=f"?sort=custom&order={next_sort_order}",
              cls="sortable-header")),
    ),
                     cls="leaderboard-row header")

    leaderboard_rows = [
        Div(Grid(
            Div(f"#{i+1} {['🥇','🥈','🥉'][i] if i < 3 else ''}",
                cls=f"rank medal-{i+1}" if i < 3 else "rank"),
            Div(entry['name']), Div(f"{entry['points']} pts", cls="points"),
            Div(f"{entry['custom_points']} pts", cls="points")),
            cls="leaderboard-row") for i, entry in enumerate(total_points)
    ]

    return Titled(
        "AoC 2024 SolveIt Leaderboard",
        Style("""
           .day-links { margin-bottom: 2rem; }
           .day-link { margin-right: 1rem; }
           .leaderboard-row { padding: 0.5rem; border-bottom: 1px solid var(--pico-secondary-focus); }
           .points { font-weight: bold; }
           .medal-1 { color: gold; }
           .medal-2 { color: silver; }
           .medal-3 { color: #cd7f32; }
           .container { max-width: 600px; margin: 0 auto; }
           .grid { display: grid; grid-template-columns: 0.2fr 1fr 0.3fr 0.3fr; gap: 1rem; }
           .sortable-header { cursor: pointer; text-decoration: underline; }
       """),
        Div(
            Div(H3("Select a Day"),
                Div(*day_links, cls="day-links"),
                H3("Total Points"),
                header_row,
                *leaderboard_rows,
                cls="container")))


@rt('/day/{day_num}')
def get(day_num: int):
    data = fetch_leaderboard()
    times = get_day_completion_times(data, day_num)

    return Titled(
        f"Day {day_num} Leaderboard",
        Style("""
           .leaderboard-row { padding: 0.5rem; border-bottom: 1px solid var(--pico-secondary-focus); }
           .time { font-family: monospace; }
           .medal-1 { color: gold; }
           .medal-2 { color: silver; }
           .medal-3 { color: #cd7f32; }
           .back-link { margin-bottom: 2rem; display: block; }
           .container { max-width: 600px; margin: 0 auto; }
           .grid { display: grid; grid-template-columns: 0.2fr 1fr 0.3fr; gap: 1rem; }
       """),
        Div(Div(
            A("← Back to Overview", href="/", cls="back-link"), *[
                Div(Grid(
                    Div(f"#{i+1} {['🥇','🥈','🥉'][i] if i < 3 else ''}",
                        cls=f"rank medal-{i+1}" if i < 3 else "rank"),
                    Div(entry['name']),
                    Div(format_time(entry['duration']), cls="time")),
                    cls="leaderboard-row") for i, entry in enumerate(times)
            ]),
            cls="container"))


serve()
