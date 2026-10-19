import { StyleSheet, View } from "react-native";

import { type Inline, parseMarkdown } from "./markdownParser";
import { Text, type TextProps } from "./Text";
import { fonts, spacing } from "./tokens";

type Props = { source: string; variant?: TextProps["variant"] };

function Inlines({ inlines, variant }: { inlines: Inline[]; variant: TextProps["variant"] }) {
  const bold = variant === "reading" ? fonts.serifSemibold : fonts.sansSemibold;
  return (
    <Text variant={variant}>
      {inlines.map((part, i) => (
        <Text
          key={i}
          variant={variant}
          style={[part.bold && { fontFamily: bold }, part.italic && { fontStyle: "italic" }]}
        >
          {part.text}
        </Text>
      ))}
    </Text>
  );
}

/** Renders lesson Markdown (restricted subset) as native text. Never HTML. */
export function Markdown({ source, variant = "reading" }: Props) {
  return (
    <View style={styles.blocks}>
      {parseMarkdown(source).map((block, i) =>
        block.kind === "paragraph" ? (
          <Inlines key={i} inlines={block.inlines} variant={variant} />
        ) : (
          <View key={i} style={styles.list} accessibilityRole="list">
            {block.items.map((item, j) => (
              <View key={j} style={styles.item}>
                <Text variant={variant} importantForAccessibility="no">
                  •
                </Text>
                <View style={styles.itemText}>
                  <Inlines inlines={item} variant={variant} />
                </View>
              </View>
            ))}
          </View>
        ),
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  blocks: { gap: spacing.md },
  list: { gap: spacing.xs },
  item: { flexDirection: "row", gap: spacing.sm },
  itemText: { flex: 1 },
});
