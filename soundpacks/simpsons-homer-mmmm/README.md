# Example: Homer Simpson "Mmmm..." pack

This directory documents the six-file pack used while developing Cursor Sound
Rotator. The recordings are not distributed by this repository because they
are third-party copyrighted media and are not covered by the project's MIT
license.

The optional `download.sh` helper fetches the files directly from their source:
[The Sound Archive](https://www.thesoundarchive.com/simpsons.asp). Review that
site's terms and use the recordings only where you have permission.

## Download and install

```bash
./soundpacks/simpsons-homer-mmmm/download.sh
./install.sh ./soundpacks/simpsons-homer-mmmm/downloads/wav
```

The helper defaults to WAV. To fetch the smaller MP3 versions instead:

```bash
./soundpacks/simpsons-homer-mmmm/download.sh mp3
./install.sh ./soundpacks/simpsons-homer-mmmm/downloads/mp3
```

Included clip names:

1. Mmmm, Beernuts
2. Mmmm, Burgers
3. Mmmm, Chocolate
4. Mmmm, Crumbled up cookie things
5. Mmmm, Organized crime
6. Mmmm, Urinal fresh

The Simpsons and Homer Simpson are trademarks of their respective owners. This
example is not affiliated with or endorsed by those owners.
