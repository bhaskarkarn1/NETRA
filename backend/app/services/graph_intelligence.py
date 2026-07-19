"""
NETRA Graph Intelligence Service — Network Analysis for Fraud Syndicates

Uses NetworkX to run real graph algorithms on the fraud entity network:
- PageRank: Identifies the most connected/important entities (kingpin nodes)
- Community Detection (Louvain): Discovers fraud syndicate clusters
- Centrality Analysis: Betweenness, degree, eigenvector centrality
- Path Analysis: Shortest paths between entities

This transforms the "Investigate" page from a static visualization into
a computed intelligence product.

References:
- Page et al., "The PageRank Citation Ranking" (1999)
- Blondel et al., "Fast unfolding of communities in large networks" (2008)
- Freeman, "Centrality in social networks" (1978)
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import GraphNode, GraphEdge

logger = logging.getLogger(__name__)


@dataclass
class RankedEntity:
    """An entity ranked by graph algorithm."""
    node_id: str
    label: str
    node_type: str
    score: float
    rank: int
    connected_cases: int

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "node_type": self.node_type,
            "score": round(self.score, 6),
            "rank": self.rank,
            "connected_cases": self.connected_cases,
        }


@dataclass
class Community:
    """A detected community/syndicate in the fraud network."""
    community_id: int
    members: list[dict]  # [{node_id, label, type}]
    size: int
    density: float  # Internal edge density
    key_entities: list[str]  # Top-ranked members by PageRank

    def to_dict(self) -> dict:
        return {
            "community_id": self.community_id,
            "members": self.members,
            "size": self.size,
            "density": round(self.density, 4),
            "key_entities": self.key_entities,
        }


@dataclass
class GraphStats:
    """Overall graph statistics."""
    total_nodes: int
    total_edges: int
    density: float
    avg_degree: float
    connected_components: int
    largest_component_size: int
    communities_detected: int

    def to_dict(self) -> dict:
        return {
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "density": round(self.density, 6),
            "avg_degree": round(self.avg_degree, 2),
            "connected_components": self.connected_components,
            "largest_component_size": self.largest_component_size,
            "communities_detected": self.communities_detected,
        }


class GraphIntelligenceService:
    """
    Run graph algorithms on the NETRA fraud network.

    Loads nodes and edges from PostgreSQL, builds a NetworkX graph,
    and computes PageRank, community detection, and centrality metrics.
    """

    async def build_graph(self, db: AsyncSession):
        """Load graph from DB and build a NetworkX DiGraph."""
        import networkx as nx

        # Load nodes
        nodes_result = await db.execute(select(GraphNode))
        nodes = nodes_result.scalars().all()

        # Load edges
        edges_result = await db.execute(select(GraphEdge))
        edges = edges_result.scalars().all()

        G = nx.DiGraph()

        for node in nodes:
            G.add_node(
                str(node.id),
                label=node.label,
                node_type=node.node_type,
                risk_score=node.risk_score or 0,
            )

        for edge in edges:
            G.add_edge(
                str(edge.source_id),
                str(edge.target_id),
                edge_type=edge.edge_type,
                weight=edge.weight or 1.0,
            )

        logger.info(f"Built graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G

    async def get_pagerank(self, db: AsyncSession, top_n: int = 10) -> list[RankedEntity]:
        """
        Compute PageRank to identify the most important entities.

        High PageRank entities are "kingpin nodes" — they connect to many
        cases and other entities, suggesting they are central to a fraud network.
        """
        import networkx as nx

        G = await self.build_graph(db)
        if G.number_of_nodes() == 0:
            return []

        # Convert to undirected for PageRank (more stable)
        G_undirected = G.to_undirected()

        try:
            scores = nx.pagerank(G_undirected, alpha=0.85, max_iter=100)
        except nx.PowerIterationFailedConvergence:
            scores = nx.pagerank(G_undirected, alpha=0.85, max_iter=500, tol=1e-04)

        # Sort and rank
        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        ranked = []
        for rank, (node_id, score) in enumerate(sorted_nodes[:top_n], 1):
            attrs = G.nodes.get(node_id, {})
            degree = G_undirected.degree(node_id)
            ranked.append(RankedEntity(
                node_id=node_id,
                label=attrs.get("label", "Unknown"),
                node_type=attrs.get("node_type", "unknown"),
                score=score,
                rank=rank,
                connected_cases=degree,
            ))

        return ranked

    async def detect_communities(self, db: AsyncSession) -> list[Community]:
        """
        Detect communities using the Louvain algorithm.

        Communities in the fraud graph represent potential syndicates —
        groups of entities (phones, accounts, suspects) that are densely
        interconnected, suggesting coordinated criminal activity.
        """
        import networkx as nx

        G = await self.build_graph(db)
        if G.number_of_nodes() < 2:
            return []

        G_undirected = G.to_undirected()

        try:
            # Louvain community detection
            communities_gen = nx.community.louvain_communities(
                G_undirected, resolution=1.0, seed=42
            )
            communities_list = list(communities_gen)
        except Exception as e:
            logger.warning(f"Louvain failed, trying greedy modularity: {e}")
            try:
                communities_gen = nx.community.greedy_modularity_communities(G_undirected)
                communities_list = list(communities_gen)
            except Exception as e2:
                logger.error(f"Community detection failed: {e2}")
                return []

        # Compute PageRank for ranking members within communities
        try:
            pr_scores = nx.pagerank(G_undirected, alpha=0.85)
        except Exception:
            pr_scores = {n: 1.0 / G.number_of_nodes() for n in G.nodes()}

        result = []
        for idx, community_nodes in enumerate(communities_list):
            if len(community_nodes) < 2:
                continue

            members = []
            for node_id in community_nodes:
                attrs = G.nodes.get(node_id, {})
                members.append({
                    "node_id": node_id,
                    "label": attrs.get("label", "Unknown"),
                    "type": attrs.get("node_type", "unknown"),
                    "pagerank": round(pr_scores.get(node_id, 0), 6),
                })

            # Sort members by PageRank
            members.sort(key=lambda x: x["pagerank"], reverse=True)

            # Compute density of the community subgraph
            subgraph = G_undirected.subgraph(community_nodes)
            density = nx.density(subgraph)

            # Top 3 key entities
            key_entities = [m["label"] for m in members[:3]]

            result.append(Community(
                community_id=idx,
                members=members,
                size=len(members),
                density=density,
                key_entities=key_entities,
            ))

        # Sort communities by size descending
        result.sort(key=lambda x: x.size, reverse=True)
        logger.info(f"Detected {len(result)} communities (size >= 2)")
        return result

    async def get_centrality(self, db: AsyncSession, top_n: int = 10) -> dict:
        """
        Compute multiple centrality measures for comprehensive entity ranking.

        - Degree centrality: How many connections an entity has
        - Betweenness centrality: How often an entity bridges different clusters
        - Eigenvector centrality: How connected an entity is to other well-connected entities
        """
        import networkx as nx

        G = await self.build_graph(db)
        if G.number_of_nodes() == 0:
            return {"degree": [], "betweenness": [], "eigenvector": []}

        G_undirected = G.to_undirected()

        # Degree centrality
        degree = nx.degree_centrality(G_undirected)

        # Betweenness centrality
        try:
            betweenness = nx.betweenness_centrality(G_undirected)
        except Exception:
            betweenness = {n: 0 for n in G.nodes()}

        # Eigenvector centrality
        try:
            eigenvector = nx.eigenvector_centrality(G_undirected, max_iter=500)
        except Exception:
            eigenvector = {n: 0 for n in G.nodes()}

        def top_entities(scores: dict) -> list[dict]:
            sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            result = []
            for node_id, score in sorted_items[:top_n]:
                attrs = G.nodes.get(node_id, {})
                result.append({
                    "node_id": node_id,
                    "label": attrs.get("label", "Unknown"),
                    "node_type": attrs.get("node_type", "unknown"),
                    "score": round(score, 6),
                })
            return result

        return {
            "degree": top_entities(degree),
            "betweenness": top_entities(betweenness),
            "eigenvector": top_entities(eigenvector),
        }

    async def get_graph_stats(self, db: AsyncSession) -> GraphStats:
        """Compute overall graph statistics."""
        import networkx as nx

        G = await self.build_graph(db)
        G_undirected = G.to_undirected()

        n_nodes = G.number_of_nodes()
        n_edges = G.number_of_edges()

        if n_nodes == 0:
            return GraphStats(
                total_nodes=0, total_edges=0, density=0,
                avg_degree=0, connected_components=0,
                largest_component_size=0, communities_detected=0,
            )

        density = nx.density(G_undirected)
        avg_degree = sum(dict(G_undirected.degree()).values()) / n_nodes if n_nodes > 0 else 0

        components = list(nx.connected_components(G_undirected))
        largest = max(len(c) for c in components) if components else 0

        # Quick community count
        try:
            communities = list(nx.community.louvain_communities(G_undirected, seed=42))
            n_communities = len([c for c in communities if len(c) >= 2])
        except Exception:
            n_communities = 0

        return GraphStats(
            total_nodes=n_nodes,
            total_edges=n_edges,
            density=density,
            avg_degree=avg_degree,
            connected_components=len(components),
            largest_component_size=largest,
            communities_detected=n_communities,
        )
