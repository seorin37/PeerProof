import sys
import zipfile
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup


ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SRC_DIR = (
    ROOT_DIR
    / "src"
)

sys.path.insert(
    0,
    str(SRC_DIR),
)

from peerproof.dart import (
    DartDocumentParser,
)


RAW_ROOT = (
    ROOT_DIR
    / "data"
    / "raw"
    / "dart"
)


def main():

    company_name = input(
        "기업명: "
    ).strip()

    report_type = input(
        "보고서 타입 "
        "(annual/semiannual/quarterly): "
    ).strip()

    company_dir = (
        RAW_ROOT
        / company_name
    )

    matches = list(
        company_dir.glob(
            f"*_{report_type}_*.zip"
        )
    )

    if not matches:

        print(
            "ZIP 파일을 찾지 못했습니다."
        )
        return

    zip_path = sorted(
        matches
    )[-1]

    print(
        "\nZIP:",
        zip_path,
    )

    parser = (
        DartDocumentParser()
    )

    with zipfile.ZipFile(
        zip_path
    ) as zf:

        docs = [
            name
            for name in zf.namelist()
            if name.lower().endswith(
                parser.DOCUMENT_EXTENSIONS
            )
        ]

        print(
            "\n문서 파일:"
        )

        for name in docs:
            print(
                " -",
                name,
            )

        for name in docs:

            raw = zf.read(
                name
            )

            decoded = (
                parser.decode_bytes(
                    raw
                )
            )

            soup = (
                parser.make_soup(
                    decoded,
                    name,
                )
            )

            counter = Counter()

            for tag in soup.find_all(
                True
            ):

                if tag.name:
                    counter[
                        str(
                            tag.name
                        ).lower()
                    ] += 1

            print()
            print(
                "=" * 70
            )

            print(
                "FILE:",
                name,
            )

            print(
                "상위 태그:"
            )

            for tag_name, count in (
                counter.most_common(40)
            ):
                print(
                    f"{tag_name:25} "
                    f"{count}"
                )

            interesting = {
                name: count
                for name, count
                in counter.items()
                if (
                    "table" in name
                    or name
                    in {
                        "tr",
                        "td",
                        "th",
                        "te",
                        "tu",
                        "row",
                        "entry",
                        "img",
                        "image",
                        "graphic",
                    }
                )
            }

            print()
            print(
                "표/이미지 관련 태그:"
            )

            print(
                interesting
            )


if __name__ == "__main__":
    main()