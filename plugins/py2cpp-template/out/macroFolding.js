"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MacroFoldingProvider = void 0;
const vscode = require("vscode");
const macroPairs_1 = require("./macroPairs");
const util_1 = require("./util");
class MacroFoldingProvider {
    provideFoldingRanges(document) {
        if (!(0, util_1.getConfig)().get("enableMacroPairs", true)) {
            return undefined;
        }
        if (!(0, util_1.getConfig)().get("enableMacroFolding", true)) {
            return undefined;
        }
        if (!(0, util_1.isTemplateDocument)(document)) {
            return undefined;
        }
        const pairs = (0, macroPairs_1.parseMacroPairs)(document.getText());
        const ranges = [];
        for (const pair of pairs) {
            if (pair.closeLine <= pair.openLine) {
                continue;
            }
            ranges.push(new vscode.FoldingRange(pair.openLine, pair.closeLine, vscode.FoldingRangeKind.Region));
        }
        return ranges;
    }
}
exports.MacroFoldingProvider = MacroFoldingProvider;
