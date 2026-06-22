"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MacroDocumentHighlightProvider = void 0;
const vscode = require("vscode");
const macroPairs_1 = require("./macroPairs");
const util_1 = require("./util");
class MacroDocumentHighlightProvider {
    provideDocumentHighlights(document, position) {
        if (!(0, util_1.getConfig)().get("enableMacroPairs", true)) {
            return undefined;
        }
        if (!(0, util_1.isTemplateDocument)(document)) {
            return undefined;
        }
        const pairs = (0, macroPairs_1.parseMacroPairs)(document.getText());
        const line = position.line;
        let target = (0, macroPairs_1.findEnclosingPair)(pairs, line);
        if (!target && (0, macroPairs_1.lineIsMacroDelimiter)(pairs, line)) {
            target = pairs.find((pair) => pair.openLine === line || pair.closeLine === line);
        }
        if (!target) {
            return undefined;
        }
        const highlights = [];
        for (const macroLine of [target.openLine, target.closeLine]) {
            const token = (0, macroPairs_1.macroTokenRange)(document.lineAt(macroLine).text, macroLine);
            if (!token) {
                continue;
            }
            highlights.push({
                range: new vscode.Range(macroLine, token.start, macroLine, token.end),
                kind: vscode.DocumentHighlightKind.Text,
            });
        }
        return highlights.length > 0 ? highlights : undefined;
    }
}
exports.MacroDocumentHighlightProvider = MacroDocumentHighlightProvider;
