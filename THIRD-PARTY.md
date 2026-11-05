# Third-party material

**Qwenputer**, by Divyansh Agrawal, MIT. The firmware builds link its `crt0.S`, `rt.h` and `rom.ld`. A copy of its `chipformer` code is in `vendor/qwenputer-riscv/`. Its licence is in `licenses/qwenputer-LICENSE`. https://github.com/divagr18/qwenputer

**Qwen3.5-4B**, Apache 2.0 according to its model card. No weights or tokenizer files are in this repo. The firmware builds embed tables derived from its tokenizer.

**MTA subway data.** Stations and track in `data/heldout/nyc/` and `web/geometry.json` are derived from the MTA's public GTFS feed. The [MTA's terms and conditions for its data feeds](https://www.mta.info/developers/terms-and-conditions) apply to that data. This project isn't affiliated with or endorsed by the MTA, and the data may be out of date.

**NYC Open Data, Borough Boundaries.** Simplified in `web/land.json`.

**US Census Bureau, cartographic boundary file `cb_2023_us_county_500k`.** Clipped and simplified in `web/near.json`.
