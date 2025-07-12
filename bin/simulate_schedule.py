from xwalk2.animation_library import AnimationLibrary
from collections import Counter
import polars as pl

if __name__ == "__main__":
  import argparse

  al = AnimationLibrary()

  parser = argparse.ArgumentParser()
  parser.add_argument("-n", type=int, default=1000, help="Number of trials")
  parser.add_argument("weights", help="Weights to use when running the simulation", choices=sorted(list(al.config.weights.keys())))
  args = parser.parse_args()

  log = []
  for n in range(args.n):
    intro, walk, outro = al.select_animation_sequence(weights=al.config.weights[args.weights], verbose=False)
    log.append([walk.image, walk.category])
  print(f"Simulation for {args.weights}")

  df = pl.DataFrame(log, orient='row', schema=['walk','category']).with_row_index()

  cats = df['category'].value_counts().sort('count', descending=True)
  cats = cats.with_columns(pct=pl.col('count')/pl.col('count').sum())
  print(cats)

  walks = df['walk'].value_counts().sort('count', descending=True)
  walks = walks.with_columns(pct=pl.col('count')/pl.col('count').sum())
  print(walks.head(10))


  
