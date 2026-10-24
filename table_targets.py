"""Hit targets on a horizontal 3-by-12 roulette number grid (3, 2, 1 top to bottom)."""

def inside_targets():
    targets=[]
    # Lines separating adjacent streets: 1/4, 2/5, 3/6, etc.
    for street in range(11):
        for column in range(3):
            targets.append(dict(key=f'split:v:{street}:{column}',kind='vertical',x=100*(street+1)/12,y=100*(2.5-column)/3))
        # Intersections: 1/2/4/5 and 2/3/5/6, etc.
        for column in range(2):
            targets.append(dict(key=f'corner:{street}:{column}',kind='corner',x=100*(street+1)/12,y=100*(2-column)/3))
    # Lines within each street: 1/2 and 2/3, etc.
    for street in range(12):
        for column in range(2):
            targets.append(dict(key=f'split:h:{street}:{column}',kind='horizontal',x=100*(street+.5)/12,y=100*(2-column)/3))
    return targets
