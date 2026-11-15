import os
queries = [
    'ytsearch1:"stock footage" traffic intersection overhead real',
    'ytsearch1:"stock footage" busy intersection cars overhead',
    'ytsearch1:traffic CCTV intersection real footage',
    'ytsearch1:highway traffic camera overhead real footage'
]
for i, q in enumerate(queries):
    print(f"Result for Query {i}:")
    os.system(f'python -m yt_dlp "{q}" --get-title')
