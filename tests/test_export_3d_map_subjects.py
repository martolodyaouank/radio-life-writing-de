from types import SimpleNamespace

from lives_on_air.analysis.export_3d_map import description_subject, subject_name


def row(**values):
    defaults = {
        "title": "",
        "display_title": "",
        "genre": "",
        "life_signal": "diary/letters",
        "cluster_label": "",
        "description": "",
        "seo_description": "",
        "long_description": "",
        "image_caption": "",
        "image_alt": "",
        "authors": "",
        "creator": "",
        "author": "",
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_description_subject_extracts_german_protagonist_phrase():
    assert (
        description_subject(
            "Ein Student aus der DDR beginnt sein fünfjähriges Studium in Charkow (Sowjetunion)."
        )
        == "Ein Student aus der DDR"
    )


def test_description_subject_extracts_english_protagonist_phrase():
    assert (
        description_subject(
            "An old woman tells of an early love for which there was no place."
        )
        == "An old woman"
    )


def test_subject_name_prefers_description_over_author_for_letters():
    record = row(
        title="Briefe an Anne",
        author="Ulrike Schünemann",
        authors="Ulrike Schünemann",
        description="Ein Student aus der DDR beginnt sein fünfjähriges Studium in Charkow (Sowjetunion).",
    )

    assert subject_name(record) == "Ein Student aus der DDR"


def test_subject_name_does_not_fall_back_to_author_for_letters():
    record = row(
        title="Koljas Briefe",
        author="Adolf Schröder",
        authors="Adolf Schröder",
        description="Eine alte Frau erzählt von einer frühen Liebe, für die es keinen Platz gab.",
    )

    assert subject_name(record) == "Eine alte Frau"


def test_subject_name_uses_author_credit_when_description_confirms_subject():
    record = row(
        title="Tagebuch meiner Töne",
        author="Pierre Henry",
        authors="Pierre Henry",
        description="Pierre Henry war der erste professionelle Komponist, der das Komponieren im traditionellen Sinne aufgab.",
    )

    assert subject_name(record) == "Pierre Henry"


def test_subject_name_extracts_named_protagonist_from_when_clause():
    record = row(
        title="Das einzig Sichere ist das Wagnis",
        author="Sylvia Rauer",
        authors="Sylvia Rauer",
        description="Als Felix Jackson, alias Felix Joachimson, 1992 90-jährig in Kalifornien stirbt, gehört er zu den wenigen Emigranten.",
    )

    assert subject_name(record) == "Felix Jackson"


def test_subject_name_extracts_named_subject_after_role():
    record = row(
        title="... is a dangerous number",
        author="Karl Bruckmaier",
        authors="Karl Bruckmaier",
        description="'Is a dangerous number' is a portrait of the playwright, critic and poet Amiri Baraka (LeRoi Jones).",
    )

    assert subject_name(record) == "Amiri Baraka"


def test_subject_name_does_not_overcapture_after_named_role_subject():
    record = row(
        title="Biographie und Liebe",
        author="Samuel Nathaniel Behrman",
        authors="Samuel Nathaniel Behrman",
        description="The painter Marion Froude portrayed famous men in East and West and made the inaccessible celebrities sit with her.",
    )

    assert subject_name(record) == "Marion Froude"


def test_subject_name_extracts_letter_writer_not_opening_noun_phrase():
    record = row(
        title="Sweet Paris reloaded",
        author='Wolf Pehlke; Alfred "23" Harth; Peter Fey',
        authors='Wolf Pehlke; Alfred "23" Harth; Peter Fey',
        description="The textual starting point of this musical radio piece, which is influenced by jazz and pop, are letters that the visual artist Wolf Pehlke from Paris, who was born in Sinzheim near Baden-Baden in 1955, wrote in 1979/1980.",
    )

    assert subject_name(record) == "Wolf Pehlke"


def test_subject_name_extracts_named_opening_protagonist_before_composer_credit():
    record = row(
        title="Achim Freyer trifft Don Giovanni am Checkpoint Charlie",
        author="Alvin Curran",
        authors="Alvin Curran",
        description="Achim Freyer has been shaping the theater world for over 50 years - as a director, painter, set and costume designer.",
    )

    assert subject_name(record) == "Achim Freyer"


def test_subject_name_uses_author_for_autobiographical_description():
    record = row(
        title="Fortsetzung einer Flucht - Ein autobiographisches Hörspiel",
        author="Werner Meyke",
        authors="Werner Meyke",
        description="This time he has created an original sound novelty: an autobiography.",
    )

    assert subject_name(record) == "Werner Meyke"


def test_subject_name_uses_named_autobiographical_author_over_adaptation_credit():
    record = row(
        title="Montauk (2/2)",
        author="Bearbeitung und Regie: Leonhard Koppelmann",
        authors="",
        description="In a collage of memories, diary excerpts, self-reflections and other autobiographical material, the Swiss writer Max Frisch dissects his life.",
    )

    assert subject_name(record) == "Max Frisch"


def test_subject_name_keeps_fictional_autobiography_with_character():
    record = row(
        title="Tristram Shandy",
        author="Laurence Sterne",
        authors="Laurence Sterne",
        description="Contrary to the title's announcement, which suggests a fictional autobiography, the reader learns little about the life of the title hero and first-person narrator Tristram.",
    )

    assert subject_name(record) == "Tristram"


def test_subject_name_extracts_story_of_subject():
    record = row(
        title="Vorname Jonas",
        author="Thomas Heise",
        authors="Thomas Heise",
        description="Die Geschichte von Jonas, der in einer Kleinstadt aufwächst.",
    )

    assert subject_name(record) == "Jonas"


def test_subject_name_trims_role_phrase_before_name():
    record = row(
        title="Maestro der Comebacks",
        author="Jean-Claude Kuner",
        authors="Jean-Claude Kuner",
        description="A portrait of Brazilian pianist and conductor João Carlos Martins, who returns after injuries.",
    )

    assert subject_name(record) == "João Carlos Martins"
