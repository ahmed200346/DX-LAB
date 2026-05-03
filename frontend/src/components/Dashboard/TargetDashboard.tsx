"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

interface Target {
  gene: string;
  protein: string;
  uniprot_id: string;
  organism?: string;
  druggability_score: number;
  mutations: string[];
  disease_context: string;
  druggability_notes: string;
  pubmed_total_count: number;
  pubmed_recent_count: number;
  pubmed_trend: string;
  evidence_tier: string;
  pubmed_url?: string;
  associated_diseases?: string[];
  pdb_ids: string[];
  alphafold?: { alphafold_url: string };
  top_pathway?: string;
  pathway_score?: number;
  pathway_profile?: {
    reactome_pathways: any[];
    kegg_pathways: any[];
    text_pathways: string[];
  };
  go_terms?: string[];
  uniprot_keywords?: string[];
  chembl_ids?: string[];
  subcellular_locs?: string[];
  function?: string;
  protein_full_name?: string;
}

interface DashboardProps {
  targets: Target[];
}

const TREND_COLORS = {
  rising: "#10b981",
  declining: "#ef4444",
  stable: "#6b7280",
};

export default function TargetDashboard({ targets }: DashboardProps) {
  const [expandedTarget, setExpandedTarget] = useState<string | null>(null);

  if (!targets || targets.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No target data available. Run a query with target extraction first.
      </div>
    );
  }

  // Summary stats
  const avgDruggability =
    targets.reduce((acc, t) => acc + (t.druggability_score || 0), 0) /
    targets.length;
  const totalPubMed = targets.reduce(
    (acc, t) => acc + (t.pubmed_total_count || 0),
    0
  );
  const trendCounts = {
    rising: targets.filter((t) => t.pubmed_trend === "rising").length,
    declining: targets.filter((t) => t.pubmed_trend === "declining").length,
    stable: targets.filter((t) => t.pubmed_trend === "stable").length,
  };

  const druggabilityData = targets.map((t) => ({
    gene: t.gene,
    druggability: (t.druggability_score || 0) * 100,
  }));

  const trendData = [
    { name: "Rising", value: trendCounts.rising, color: TREND_COLORS.rising },
    { name: "Declining", value: trendCounts.declining, color: TREND_COLORS.declining },
    { name: "Stable", value: trendCounts.stable, color: TREND_COLORS.stable },
  ].filter((d) => d.value > 0);

  const pubmedCountData = targets.map((t) => ({
    gene: t.gene,
    publications: t.pubmed_total_count || 0,
  }));

  const toggleExpand = (gene: string) => {
    setExpandedTarget(expandedTarget === gene ? null : gene);
  };

  return (
    <div className="space-y-8">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6 border border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Targets</h3>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">{targets.length}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Avg. Druggability Score
          </h3>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {(avgDruggability * 100).toFixed(1)}%
          </p>
          <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full"
              style={{ width: `${avgDruggability * 100}%` }}
            />
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Total PubMed Mentions
          </h3>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">
            {totalPubMed.toLocaleString()}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
            Druggability Score by Target
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={druggabilityData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} unit="%" />
              <YAxis type="category" dataKey="gene" width={80} />
              <Tooltip formatter={(value) => `${value}%`} />
              <Bar dataKey="druggability" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {trendData.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
              PubMed Trend Distribution
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={trendData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label
                >
                  {trendData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
          PubMed Publications per Target
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={pubmedCountData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="gene" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="publications" fill="#10b981" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Detailed Target Cards */}
      <div>
        <h3 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">
          Detailed Target Information
        </h3>
        <div className="grid grid-cols-1 gap-6">
          {targets.map((target) => {
            const isExpanded = expandedTarget === target.gene;
            return (
              <div
                key={target.gene}
                className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 overflow-hidden"
              >
                {/* Header always visible */}
                <div
                  className="p-6 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750 transition"
                  onClick={() => toggleExpand(target.gene)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                        {target.gene}
                      </h4>
                      <p className="text-md text-gray-600 dark:text-gray-300 mt-1">
                        {target.protein_full_name || target.protein}
                      </p>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm">
                        <span className="text-gray-500">UniProt: {target.uniprot_id}</span>
                        {target.organism && (
                          <span className="text-gray-500">Organism: {target.organism}</span>
                        )}
                        <span className="text-gray-500">
                          PDB structures: {target.pdb_ids?.length || 0}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="mb-1">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                          {target.evidence_tier || "N/A"} evidence
                        </span>
                      </div>
                      <button className="text-sm text-primary-600 dark:text-primary-400">
                        {isExpanded ? "Show less ▲" : "Show more ▼"}
                      </button>
                    </div>
                  </div>

                  {/* Compact always-visible metrics */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600 dark:text-gray-400">Druggability Score</span>
                        <span className="font-medium">
                          {((target.druggability_score || 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-600 rounded-full"
                          style={{ width: `${(target.druggability_score || 0) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-600 dark:text-gray-400">PubMed trend:</span>
                        <span
                          className={`inline-flex items-center gap-1 text-sm font-medium ${
                            target.pubmed_trend === "rising"
                              ? "text-green-600"
                              : target.pubmed_trend === "declining"
                              ? "text-red-600"
                              : "text-gray-600"
                          }`}
                        >
                          {target.pubmed_trend === "rising" && "📈"}
                          {target.pubmed_trend === "declining" && "📉"}
                          {target.pubmed_trend === "stable" && "➡️"}
                          {target.pubmed_trend}
                        </span>
                      </div>
                      <div className="text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Publications:</span>{" "}
                        <span className="font-medium">
                          {target.pubmed_total_count?.toLocaleString() || 0}
                        </span>
                      </div>
                    </div>
                  </div>

                  {!isExpanded && (
                    <div className="mt-3 text-sm text-gray-500">
                      Click to see mutations, pathways, structural details, diseases, and more.
                    </div>
                  )}
                </div>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-gray-200 dark:border-gray-700 p-6 bg-gray-50 dark:bg-gray-750 space-y-6">
                    {/* Mutations & Disease */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h5 className="font-semibold text-gray-800 dark:text-gray-200">Mutations</h5>
                        {target.mutations && target.mutations.length > 0 ? (
                          <div className="flex flex-wrap gap-2 mt-1">
                            {target.mutations.map((m) => (
                              <span
                                key={m}
                                className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                              >
                                {m}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-gray-500 text-sm mt-1">None specified</p>
                        )}
                      </div>
                      <div>
                        <h5 className="font-semibold text-gray-800 dark:text-gray-200">Disease Context</h5>
                        <p className="text-sm mt-1 text-gray-700 dark:text-gray-300">
                          {target.disease_context || "Not available"}
                        </p>
                      </div>
                    </div>

                    {/* Druggability Notes */}
                    {target.druggability_notes && (
                      <div>
                        <h5 className="font-semibold text-gray-800 dark:text-gray-200">Druggability Notes</h5>
                        <p className="text-sm mt-1 text-gray-700 dark:text-gray-300">
                          {target.druggability_notes}
                        </p>
                      </div>
                    )}

                    {/* PubMed Details */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h5 className="font-semibold text-gray-800 dark:text-gray-200">PubMed Statistics</h5>
                        <ul className="text-sm mt-1 space-y-1">
                          <li>Total publications: {target.pubmed_total_count?.toLocaleString()}</li>
                          <li>Recent (last 5 years): {target.pubmed_recent_count?.toLocaleString()}</li>
                          <li>Evidence tier: <span className="font-medium">{target.evidence_tier}</span></li>
                          <li>
                            <a
                              href={target.pubmed_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:underline"
                            >
                              Search PubMed →
                            </a>
                          </li>
                        </ul>
                      </div>
                      <div>
                        <h5 className="font-semibold text-gray-800 dark:text-gray-200">Pathways</h5>
                        <div className="text-sm mt-1">
                          <p>
                            Top pathway:{" "}
                            <span className="font-medium">
                              {target.top_pathway || "N/A"} (score: {target.pathway_score?.toFixed(3) || "N/A"})
                            </span>
                          </p>
                          {target.pathway_profile && (
                            <div className="mt-2 text-gray-600 dark:text-gray-400">
                              <p>Reactome pathways: {target.pathway_profile.reactome_pathways?.length || 0}</p>
                              <p>KEGG pathways: {target.pathway_profile.kegg_pathways?.length || 0}</p>
                              {target.pathway_profile.text_pathways?.length > 0 && (
                                <p>Text‑mined: {target.pathway_profile.text_pathways.join(", ")}</p>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Associated Diseases */}
                    {target.associated_diseases && target.associated_diseases.length > 0 && (
                      <div>
                        <h5 className="font-semibold text-gray-800 dark:text-gray-200">Associated Diseases</h5>
                        <div className="flex flex-wrap gap-2 mt-1">
                          {target.associated_diseases.slice(0, 8).map((d) => (
                            <span key={d} className="text-xs bg-gray-200 dark:bg-gray-700 px-2 py-1 rounded">
                              {d}
                            </span>
                          ))}
                          {target.associated_diseases.length > 8 && (
                            <span className="text-xs text-gray-500">
                              +{target.associated_diseases.length - 8} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Structural Links */}
                    <div className="flex flex-wrap gap-4">
                      {target.uniprot_id && (
                        <a
                          href={`https://www.uniprot.org/uniprot/${target.uniprot_id}`}
                          target="_blank"
                          className="text-blue-600 hover:underline text-sm"
                        >
                          UniProt entry →
                        </a>
                      )}
                      {target.pdb_ids && target.pdb_ids.length > 0 && (
                        <a
                          href={`https://www.rcsb.org/search?q=${target.gene}`}
                          target="_blank"
                          className="text-blue-600 hover:underline text-sm"
                        >
                          Search PDB →
                        </a>
                      )}
                      {target.alphafold?.alphafold_url && (
                        <a
                          href={target.alphafold.alphafold_url}
                          target="_blank"
                          className="text-blue-600 hover:underline text-sm"
                        >
                          AlphaFold →
                        </a>
                      )}
                    </div>

                    {/* Additional biological info – collapsible inside expanded */}
                    <details className="text-sm">
                      <summary className="cursor-pointer font-semibold text-gray-700 dark:text-gray-300">
                        🧬 Molecular details (GO terms, Keywords, Subcellular location)
                      </summary>
                      <div className="mt-3 space-y-3 pl-2">
                        {target.subcellular_locs && target.subcellular_locs.length > 0 && (
                          <div>
                            <h6 className="font-medium">Subcellular location</h6>
                            <p className="text-gray-600 dark:text-gray-400">
                              {target.subcellular_locs.join("; ")}
                            </p>
                          </div>
                        )}
                        {target.go_terms && target.go_terms.length > 0 && (
                          <div>
                            <h6 className="font-medium">GO terms (selected)</h6>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {target.go_terms.slice(0, 10).map((go) => (
                                <span key={go} className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                                  {go}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {target.uniprot_keywords && target.uniprot_keywords.length > 0 && (
                          <div>
                            <h6 className="font-medium">UniProt keywords</h6>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {target.uniprot_keywords.slice(0, 10).map((kw) => (
                                <span key={kw} className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                                  {kw}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {target.chembl_ids && target.chembl_ids.length > 0 && (
                          <div>
                            <h6 className="font-medium">ChEMBL IDs</h6>
                            <div className="flex flex-wrap gap-2 mt-1">
                              {target.chembl_ids.map((c) => (
                                <a
                                  key={c}
                                  href={`https://www.ebi.ac.uk/chembl/compound_report_card/${c}/`}
                                  target="_blank"
                                  className="text-xs text-blue-600 hover:underline"
                                >
                                  {c}
                                </a>
                              ))}
                            </div>
                          </div>
                        )}
                        {target.function && (
                          <div>
                            <h6 className="font-medium">Function</h6>
                            <p className="text-gray-600 dark:text-gray-400 text-sm">
                              {target.function.length > 300
                                ? target.function.substring(0, 300) + "..."
                                : target.function}
                            </p>
                          </div>
                        )}
                      </div>
                    </details>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}