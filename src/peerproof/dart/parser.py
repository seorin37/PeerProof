from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag


class DartDocumentParser:
    """
    DART 공시 원문 ZIP 구조 보존 파서.

    처리 대상
    ---------
    1. 일반 텍스트
    2. 표
    3. 이미지

    표는 Markdown + JSON으로 보존하고,
    이미지는 참조정보 + 실제 이미지 파일을 보존한다.
    """

    DOCUMENT_EXTENSIONS = (
        ".xml",
        ".html",
        ".htm",
        ".xhtml",
    )

    IMAGE_EXTENSIONS = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
    )

    # DART 원문에서 표를 표현할 가능성이 있는 태그
    TABLE_TAGS = {
        "table",
        "table-group",
    }

    ROW_TAGS = {
        "tr",
        "row",
    }

    CELL_TAGS = {
        "td",
        "th",
        "te",
        "tu",
        "entry",
    }

    IMAGE_TAGS = {
        "img",
        "image",
        "graphic",
    }

    # ============================================================
    # 기본 유틸
    # ============================================================

    @staticmethod
    def tag_name(tag: Tag) -> str:
        """
        XML/HTML 태그명을 항상 소문자로 통일해서 반환.
        """

        if not getattr(tag, "name", None):
            return ""

        return str(tag.name).lower()

    @staticmethod
    def decode_bytes(raw: bytes) -> str:
        """
        DART 문서 byte decoding.
        """

        for encoding in (
            "utf-8",
            "cp949",
            "euc-kr",
        ):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode(
            "utf-8",
            errors="ignore",
        )

    @staticmethod
    def clean_inline_text(text: str) -> str:

        text = text.replace("\xa0", " ")
        text = text.replace("\u200b", "")
        text = text.replace("\ufeff", "")
        text = text.replace("\t", " ")

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    @staticmethod
    def clean_document_text(text: str) -> str:

        lines = []

        previous_blank = False

        for raw_line in text.splitlines():

            line = raw_line.strip()

            if not line:

                if not previous_blank:
                    lines.append("")

                previous_blank = True

            else:
                lines.append(line)
                previous_blank = False

        text = "\n".join(lines)

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    # ============================================================
    # XML / HTML
    # ============================================================

    @staticmethod
    def is_xml_document(
        document: str,
        filename: str | None = None,
    ) -> bool:

        if filename:

            suffix = (
                Path(filename)
                .suffix
                .lower()
            )

            if suffix in {
                ".xml",
                ".xhtml",
            }:
                return True

        head = document.lstrip()[:1000].lower()

        return head.startswith(
            "<?xml"
        )

    @classmethod
    def make_soup(
        cls,
        document: str,
        filename: str | None = None,
    ) -> BeautifulSoup:

        parser = (
            "xml"
            if cls.is_xml_document(
                document,
                filename,
            )
            else "lxml"
        )

        return BeautifulSoup(
            document,
            parser,
        )

    # ============================================================
    # 태그 찾기
    # ============================================================

    @classmethod
    def find_tags(
        cls,
        root: Tag | BeautifulSoup,
        names: set[str],
        recursive: bool = True,
    ):

        names = {
            name.lower()
            for name in names
        }

        return root.find_all(
            lambda tag:
                cls.tag_name(tag)
                in names,
            recursive=recursive,
        )

    # ============================================================
    # 표
    # ============================================================

    @classmethod
    def find_tables(
        cls,
        soup: BeautifulSoup,
    ) -> list[Tag]:
        """
        TABLE, TABLE-GROUP 등 대소문자 무관하게 탐색.

        TABLE-GROUP 안에 실제 TABLE이 있으면
        실제 TABLE만 사용해서 중복을 방지한다.
        """

        candidates = cls.find_tags(
            soup,
            cls.TABLE_TAGS,
        )

        tables = []

        for candidate in candidates:

            name = cls.tag_name(
                candidate
            )

            # 실제 table 우선
            if name == "table":
                tables.append(
                    candidate
                )
                continue

            # TABLE-GROUP 안에 TABLE이 없을 때만 자체 표로 처리
            nested_tables = cls.find_tags(
                candidate,
                {"table"},
            )

            if not nested_tables:
                tables.append(
                    candidate
                )

        return tables

    @classmethod
    def extract_rows(
        cls,
        table: Tag,
    ) -> list[Tag]:
        """
        표 내부 행 탐색.

        TR/ROW가 없더라도 TE/TU 계열 구조가 있으면
        상위 부모를 행으로 추정한다.
        """

        rows = cls.find_tags(
            table,
            cls.ROW_TAGS,
        )

        if rows:
            return rows

        # DART XML 특수 구조 fallback
        cells = cls.find_tags(
            table,
            cls.CELL_TAGS,
        )

        parent_rows = []

        seen = set()

        for cell in cells:

            parent = cell.parent

            if (
                parent is not None
                and id(parent) not in seen
            ):
                seen.add(
                    id(parent)
                )

                parent_rows.append(
                    parent
                )

        return parent_rows

    @classmethod
    def extract_cells(
        cls,
        row: Tag,
    ) -> list[Tag]:

        cells = cls.find_tags(
            row,
            cls.CELL_TAGS,
            recursive=False,
        )

        # 직접 자식이 아닐 경우 fallback
        if not cells:

            cells = cls.find_tags(
                row,
                cls.CELL_TAGS,
                recursive=True,
            )

        return cells

    @classmethod
    def parse_table(
        cls,
        table: Tag,
        table_id: str,
    ) -> dict[str, Any]:

        parsed_rows = []

        rows = cls.extract_rows(
            table
        )

        for row in rows:

            cells = cls.extract_cells(
                row
            )

            parsed_cells = []

            for cell in cells:

                text = cls.clean_inline_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )

                colspan = (
                    cell.get("colspan")
                    or cell.get("cols")
                    or cell.get("colnum")
                    or 1
                )

                rowspan = (
                    cell.get("rowspan")
                    or cell.get("rows")
                    or 1
                )

                try:
                    colspan = int(
                        colspan
                    )
                except Exception:
                    colspan = 1

                try:
                    rowspan = int(
                        rowspan
                    )
                except Exception:
                    rowspan = 1

                parsed_cells.append(
                    {
                        "text": text,
                        "colspan": colspan,
                        "rowspan": rowspan,
                    }
                )

            if parsed_cells:
                parsed_rows.append(
                    parsed_cells
                )

        return {
            "table_id": table_id,
            "rows": parsed_rows,
        }

    @classmethod
    def table_to_markdown(
        cls,
        table_data: dict[str, Any],
    ) -> str:

        rows = table_data.get(
            "rows",
            [],
        )

        if not rows:
            return ""

        converted = []

        for row in rows:

            output_row = []

            for cell in row:

                value = (
                    cell.get(
                        "text",
                        "",
                    )
                    .replace(
                        "|",
                        "\\|",
                    )
                )

                output_row.append(
                    value
                )

                colspan = max(
                    1,
                    int(
                        cell.get(
                            "colspan",
                            1,
                        )
                    ),
                )

                for _ in range(
                    colspan - 1
                ):
                    output_row.append("")

            converted.append(
                output_row
            )

        max_columns = max(
            len(row)
            for row in converted
        )

        normalized = []

        for row in converted:

            normalized.append(
                row
                + [""] * (
                    max_columns
                    - len(row)
                )
            )

        markdown = [
            "| "
            + " | ".join(
                normalized[0]
            )
            + " |",

            "| "
            + " | ".join(
                ["---"] * max_columns
            )
            + " |",
        ]

        for row in normalized[1:]:

            markdown.append(
                "| "
                + " | ".join(row)
                + " |"
            )

        return "\n".join(
            markdown
        )

    # ============================================================
    # 이미지
    # ============================================================

    @classmethod
    def find_images(
        cls,
        soup: BeautifulSoup,
    ) -> list[Tag]:

        return cls.find_tags(
            soup,
            cls.IMAGE_TAGS,
        )

    @classmethod
    def parse_images(
        cls,
        soup: BeautifulSoup,
    ) -> list[dict[str, Any]]:

        results = []

        images = cls.find_images(
            soup
        )

        for index, image in enumerate(
            images,
            start=1,
        ):

            src = (
                image.get("src")
                or image.get("href")
                or image.get("xlink:href")
                or image.get("file")
                or image.get("filename")
                or ""
            )

            parent_text = ""

            if image.parent:

                parent_text = (
                    cls.clean_inline_text(
                        image.parent.get_text(
                            " ",
                            strip=True,
                        )
                    )[:1000]
                )

            results.append(
                {
                    "image_id": (
                        f"image_{index:04d}"
                    ),
                    "tag": cls.tag_name(
                        image
                    ),
                    "source": src,
                    "alt": image.get(
                        "alt",
                        "",
                    ),
                    "title": image.get(
                        "title",
                        "",
                    ),
                    "nearby_text": (
                        parent_text
                    ),
                }
            )

        return results

    # ============================================================
    # 전체 문서 파싱
    # ============================================================

    @classmethod
    def parse_document(
        cls,
        document: str,
        filename: str | None = None,
    ) -> dict[str, Any]:

        soup = cls.make_soup(
            document,
            filename,
        )

        for tag in cls.find_tags(
            soup,
            {
                "script",
                "style",
                "noscript",
            },
        ):
            tag.decompose()

        # --------------------------------------
        # 표
        # --------------------------------------

        tables = []

        table_tags = cls.find_tables(
            soup
        )

        for index, table in enumerate(
            table_tags,
            start=1,
        ):

            table_id = (
                f"table_{index:04d}"
            )

            parsed = cls.parse_table(
                table,
                table_id,
            )

            # 비어있는 가짜 표 제외
            if not parsed["rows"]:
                continue

            parsed[
                "markdown"
            ] = cls.table_to_markdown(
                parsed
            )

            tables.append(
                parsed
            )

            placeholder = (
                soup.new_tag("p")
            )

            placeholder.string = (
                f"[[TABLE:{table_id}]]"
            )

            table.replace_with(
                placeholder
            )

        # --------------------------------------
        # 이미지
        # --------------------------------------

        images = cls.parse_images(
            soup
        )

        image_tags = cls.find_images(
            soup
        )

        for index, image in enumerate(
            image_tags,
            start=1,
        ):

            image_id = (
                f"image_{index:04d}"
            )

            placeholder = (
                soup.new_tag("p")
            )

            placeholder.string = (
                f"[[IMAGE:{image_id}]]"
            )

            image.replace_with(
                placeholder
            )

        # --------------------------------------
        # 텍스트
        # --------------------------------------

        text = soup.get_text(
            separator="\n",
        )

        text = cls.clean_document_text(
            text
        )

        markdown = text

        # 표 다시 삽입
        for table in tables:

            marker = (
                f"[[TABLE:"
                f"{table['table_id']}"
                f"]]"
            )

            markdown = markdown.replace(
                marker,
                (
                    "\n\n"
                    f"<!-- {table['table_id']} -->"
                    "\n"
                    f"{table['markdown']}"
                    "\n\n"
                ),
            )

        # 이미지 위치 표시
        for image in images:

            marker = (
                f"[[IMAGE:"
                f"{image['image_id']}"
                f"]]"
            )

            markdown = markdown.replace(
                marker,
                (
                    "\n\n"
                    f"[IMAGE: "
                    f"{image['image_id']}]"
                    "\n\n"
                ),
            )

        markdown = (
            cls.clean_document_text(
                markdown
            )
        )

        return {
            "text": text,
            "markdown": markdown,
            "tables": tables,
            "images": images,
        }

    # ============================================================
    # ZIP 문서
    # ============================================================

    @classmethod
    def extract_documents_from_zip(
        cls,
        zip_path: str | Path,
    ) -> list[dict[str, Any]]:

        zip_path = Path(
            zip_path
        )

        if not zip_path.exists():

            raise FileNotFoundError(
                f"ZIP 파일이 없습니다: "
                f"{zip_path}"
            )

        documents = []

        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as zip_file:

            for name in (
                zip_file.namelist()
            ):

                if not name.lower().endswith(
                    cls.DOCUMENT_EXTENSIONS
                ):
                    continue

                raw = zip_file.read(
                    name
                )

                decoded = cls.decode_bytes(
                    raw
                )

                parsed = cls.parse_document(
                    decoded,
                    filename=name,
                )

                documents.append(
                    {
                        "filename": name,
                        "text": parsed[
                            "text"
                        ],
                        "markdown": parsed[
                            "markdown"
                        ],
                        "tables": parsed[
                            "tables"
                        ],
                        "images": parsed[
                            "images"
                        ],
                        "length": len(
                            parsed["text"]
                        ),
                    }
                )

        return documents

    @classmethod
    def extract_main_document(
        cls,
        zip_path: str | Path,
    ) -> dict[str, Any]:

        documents = (
            cls.extract_documents_from_zip(
                zip_path
            )
        )

        if not documents:

            raise RuntimeError(
                "ZIP 내부에 XML/HTML "
                "문서가 없습니다."
            )

        documents.sort(
            key=lambda x: x[
                "length"
            ],
            reverse=True,
        )

        return documents[0]

    # ============================================================
    # ZIP 내부 실제 이미지
    # ============================================================

    @classmethod
    def extract_image_files(
        cls,
        zip_path: str | Path,
        output_dir: str | Path,
    ) -> list[dict[str, Any]]:

        zip_path = Path(
            zip_path
        )

        output_dir = Path(
            output_dir
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        extracted = []

        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as zip_file:

            for name in (
                zip_file.namelist()
            ):

                suffix = (
                    Path(name)
                    .suffix
                    .lower()
                )

                if suffix not in (
                    cls.IMAGE_EXTENSIONS
                ):
                    continue

                raw = zip_file.read(
                    name
                )

                filename = (
                    Path(name).name
                )

                output_path = (
                    output_dir
                    / filename
                )

                counter = 1

                while output_path.exists():

                    stem = (
                        output_path.stem
                    )

                    suffix = (
                        output_path.suffix
                    )

                    output_path = (
                        output_dir
                        / (
                            f"{stem}_"
                            f"{counter}"
                            f"{suffix}"
                        )
                    )

                    counter += 1

                with open(
                    output_path,
                    "wb",
                ) as file:

                    file.write(raw)

                extracted.append(
                    {
                        "zip_path": name,
                        "filename": (
                            output_path.name
                        ),
                        "output_path": str(
                            output_path
                        ),
                    }
                )

        return extracted