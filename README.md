# second-hand-hunter

Searches second-hand sites every day for items that match a spec you write,
and gives you one page to review them and mark them as viewed.

- **A hunt** is one spec file: search words, max price, max distance, size limits,
  and must-haves in plain English. Any item works (sofa, bike, desk...).
- **Sites:** eBay, Gumtree, Preloved daily. Facebook Marketplace only on request,
  through your own browser.
- Each listing is marked fits / doesn't fit / unknown, with a reason.

## Your info stays local

`profiles/` (your postcode and hunts) and `data/` (listings found) are gitignored.

## Set up

```sh
mkdir -p profiles/<you> && cp -r examples/* profiles/<you>/
# edit profiles/<you>/profile.toml and profiles/<you>/hunts/*.toml
```

Status: early. Spec format done; site search, review page and daily run to come.
