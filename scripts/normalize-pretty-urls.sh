#!/usr/bin/env sh

set -eu

# The replacements are ASCII-only; a portable C locale avoids host-specific
# locale failures in minimal render environments.
LC_ALL=C
LANG=C
export LC_ALL LANG

site_dir="${QUARTO_PROJECT_OUTPUT_DIR:-_site}"

if [ ! -d "$site_dir" ]; then
  exit 0
fi

# Quarto emits clean canonical URLs for directory index pages, while its
# sitemap, navigation, and search index normally retain index.html. Keep all
# of those signals aligned with the canonical trailing-slash URLs. This pass
# also makes Quarto's generated navigation controls correct without requiring
# JavaScript to repair their semantics after load.
find "$site_dir" -type f -name '*.html' -exec \
  perl -0pi -e '
    s{index\.html(?=(?:[?#][^\"]*)?\")}{}g;

    my $helpers = qq{<span id="page-top" class="page-top-anchor" aria-hidden="true"></span>\n<a class="skip-link" href="#quarto-document-content">Skip to main content</a>};
    if (s{<span id="page-top" class="page-top-anchor" aria-hidden="true"></span>\s*<a class="skip-link" href="#quarto-document-content">Skip to main content</a>\s*}{}s) {
      s{(<body\b[^>]*>)}{$1\n$helpers}s;
    }

    s{(<button class="navbar-toggler"[^>]*?)\srole="menu"}{$1}g;
    s{<a onclick="window\.scrollTo\(0, 0\); return false;" role="button" id="quarto-back-to-top">}{<a href="#page-top" id="quarto-back-to-top">}g;
    s{(<main class="content" id="quarto-document-content")(?![^>]*\btabindex=)}{$1 tabindex="-1"}g;
  ' {} +

if [ -f "$site_dir/search.json" ]; then
  perl -MJSON::PP -0pi -e '
    my $json = JSON::PP->new->utf8;
    my $records = $json->decode($_);
    die "search.json must contain a JSON array\n" unless ref($records) eq "ARRAY";

    my %seen_href;
    my @unique_records;

    # Work backwards so that, when Quarto has appended a refreshed record,
    # the newest content and its native index.html objectID survive.
    for my $record (reverse @{$records}) {
      if (ref($record) eq "HASH" && defined($record->{href})) {
        # objectID is the stable MiniSearch record key. Quarto emits it with
        # index.html, so leave it untouched and clean only the navigable URL.
        $record->{href} =~ s{(^|/)index\.html(?=([?#]|$))}
                            {length($1) ? $1 : "/"}ge;

        # A destination anchor should yield one search result. Quarto can
        # retain duplicate records after incremental renders.
        next if $seen_href{$record->{href}}++;
      }

      unshift @unique_records, $record;
    }

    $_ = JSON::PP->new
      ->utf8
      ->canonical
      ->pretty
      ->indent_length(2)
      ->encode(\@unique_records);
  ' "$site_dir/search.json"
fi

if [ -f "$site_dir/sitemap.xml" ]; then
  perl -0pi -e '
    s{/index\.html</loc>}{/</loc>}g;
    my %seen;
    s{(\s*<url>\s*<loc>([^<]+)</loc>.*?</url>)}
     {$seen{$2}++ ? "" : $1}gse;
  ' "$site_dir/sitemap.xml"
fi
