from __future__ import annotations

import json
from pathlib import Path
import networkx as nx
from pyvis.network import Network


class GraphEngine:
    def __init__(self) -> None:
        self.graph = nx.Graph()

    def add_relationship(self, source: str, target: str, label: str = "related") -> None:
        self.graph.add_node(source, title=source)
        self.graph.add_node(target, title=target)
        self.graph.add_edge(source, target, label=label)

    def build_from_findings(self, target: str, findings: list[dict]) -> None:
        self.graph.add_node(target, title=target, group="target")
        for record in findings:
            node = record.get("source", record.get("title", "unknown"))
            self.graph.add_node(node, title=node)
            self.graph.add_edge(target, node, label=record.get("category", "finding"))

    def export_html(self, path: Path) -> Path:
        net = Network(height="750px", width="100%", directed=False)
        for node, data in self.graph.nodes(data=True):
            net.add_node(node, label=node, title=data.get("title", node))
        for u, v, data in self.graph.edges(data=True):
            net.add_edge(u, v, title=data.get("label", ""), label=data.get("label", ""))
        net.show(str(path))
        return path

    def export_json(self, path: Path) -> Path:
        data = {
            "nodes": [{"id": node, **attrs} for node, attrs in self.graph.nodes(data=True)],
            "edges": [{"source": u, "target": v, **attrs} for u, v, attrs in self.graph.edges(data=True)]
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def export_png(self, path: Path) -> Path:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise RuntimeError("matplotlib is required to export PNG graphs")

        plt.figure(figsize=(10, 8))
        pos = nx.spring_layout(self.graph, seed=42)
        nx.draw(self.graph, pos, with_labels=True, node_color="#1f78b4", edge_color="#bbbbbb", node_size=650, font_size=10)
        plt.savefig(path, dpi=150)
        plt.close()
        return path
