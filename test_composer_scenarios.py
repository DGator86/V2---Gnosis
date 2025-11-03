#!/usr/bin/env python3
import json
import subprocess

print("=" * 60)
print("Testing Agent + Composer Scenarios")
print("=" * 60)

scenarios = [
    {
        "name": "Scenario 1: Strong Uptrend",
        "price": 453.00,
        "bar": "2025-11-03T10:00:00",
        "volume": 8000
    },
    {
        "name": "Scenario 2: Downtrend",
        "price": 449.50,
        "bar": "2025-11-03T11:00:00",
        "volume": 6000
    },
    {
        "name": "Scenario 3: High Volume Breakout",
        "price": 452.50,
        "bar": "2025-11-03T12:00:00",
        "volume": 15000
    },
    {
        "name": "Scenario 4: Low Volume Drift",
        "price": 451.65,
        "bar": "2025-11-03T13:00:00",
        "volume": 1500
    }
]

for scenario in scenarios:
    print(f"\n{scenario['name']}")
    print("-" * 40)
    
    # Make the API call
    url = f"http://127.0.0.1:8000/run_bar/SPY?price={scenario['price']}&bar={scenario['bar']}&volume={scenario['volume']}"
    
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", url],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        idea = data.get("idea", {})
        
        print(f"Take Trade: {idea.get('take_trade', False)}")
        if idea.get("take_trade"):
            print(f"Direction: {idea.get('direction')}")
            print(f"Confidence: {idea.get('confidence'):.3f}")
            print(f"Size Hint: {idea.get('position_sizing_hint'):.3f}")
            print(f"Time Stop: {idea.get('time_stop_bars')} bars")
            if idea.get("rationale"):
                print(f"Primary Driver: {idea['rationale'].get('primary_driver')}")
        else:
            print(f"Reason: {idea.get('reason')}")
            if idea.get("scores"):
                print(f"Scores: Up={idea['scores']['up']:.2f}, Down={idea['scores']['down']:.2f}")
        
        # Show agent views
        print("\nAgent Views:")
        for view in idea.get("views", []):
            print(f"  {view['agent']:10} Bias={view['dir_bias']:+.1f} Conf={view['confidence']:.2f} Thesis={view['thesis']}")
    else:
        print(f"Error: {result.stderr}")