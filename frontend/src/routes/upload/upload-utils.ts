interface SelectableTag {
    id: string;
    label: string;
}

export function createSelection(
    tags: Pick<SelectableTag, "id">[],
): Record<string, boolean> {
    return Object.fromEntries(tags.map((tag) => [tag.id, false]));
}

export function selectedCountOf(
    tags: Pick<SelectableTag, "id">[],
    selection: Record<string, boolean>,
): number {
    return tags.filter((tag) => selection[tag.id]).length;
}

export function selectedLabels(
    tags: SelectableTag[],
    selection: Record<string, boolean>,
): string[] {
    return tags.filter((tag) => selection[tag.id]).map((tag) => tag.label);
}
