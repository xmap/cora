"""`ClosedValueObject`: marker for a frozen VO the record exporter may
KEEP whole rather than resolve field by field.

Per `project_record_export_v3.md` F5, the generated redaction
disposition table (`tools/gen_record_dispositions.py`) resolves a field
by its DECLARED TYPE. A frozen value object normally RECURSES: each of
its own fields gets classified in turn, and a bare `str` field inside it
drops by the same fail-closed default as everywhere else. That is
correct for a VO like `DatasetEncoding`, whose `media_type` is a loose,
unvalidated string with no closed range.

It is the WRONG answer for a VO whose constructor closes every field's
range completely: a hex digest is a fixed-length, fixed-charset string,
and a checksum algorithm tag is drawn from a short closed set. Neither
can carry free text, so dropping them is not caution, it is the specific
defect this marker exists to fix: the record's own checksum, dropped by
the same rule that correctly protects an operator's free-text comment.

Subclass `ClosedValueObject` ONLY when EVERY field of the VO is closed
by construction: a fixed-length charset check (a hex digest), a closed
literal set, a bounded number, another `ClosedValueObject`. If any field
could carry unconstrained text (a name, a free-form reason, a URI), do
not use this marker; let the field recurse and drop like any other.

The generator checks this marker BEFORE recursing into a value object's
fields (see `_classify` in `tools/gen_record_dispositions.py`) and, when
it matches, emits `keep:closed:<ClassName>` for the whole VO. At
export time this keeps the VO's rendered form (already a dict of JSON
primitives) verbatim, exactly like any other `keep:*` disposition.

This is a marker only: it adds no fields, no methods, and no runtime
behavior. It exists purely so a build-time tool can ask a type object
"does this VO close its own range?" without hand-maintaining a list of
class names to keep.

Nothing checks the claim mechanically. Whether a subclass truly closes
every field is enforced today by code review at subclass-creation time
plus review of the generated table's diff, not by a fitness test:
`DatasetChecksum`, the only subclass as of this writing, is covered by
direct unit tests of its own `__post_init__` rejection paths (see
`tests/unit/data/test_dataset.py`), which is a proportionate check for
one instance. Rule of three: once a SECOND subclass exists, add a
fitness test that enumerates every `ClosedValueObject` subclass and
verifies each field's own validation actually closes it (a property
test over arbitrary strings/numbers is one way), rather than trusting
the marker and this docstring indefinitely.
"""

__all__ = ["ClosedValueObject"]


class ClosedValueObject:
    """Marker base for a frozen VO whose constructor closes every
    field's range. See module docstring for the criterion and the
    consequence of getting it wrong.
    """

    __slots__ = ()
