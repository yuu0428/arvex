import { createClient } from "@libsql/client";
import { MDXRemote } from "next-mdx-remote/rsc";
import { notFound } from "next/navigation";
import { proposalComponents } from "@/components/proposal/registry";
import { SmoothScroll } from "@/components/proposal/motion/SmoothScroll";
import { MotionRoot } from "@/components/proposal/motion/MotionRoot";

function getDb() {
  return createClient({
    url: process.env.TURSO_DATABASE_URL!,
    authToken: process.env.TURSO_AUTH_TOKEN,
  });
}

type ProposalRow = {
  mdx: string | null;
  expires_at: string | null;
};

export default async function ProposalPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const result = await getDb().execute({
    sql: "SELECT mdx, expires_at FROM proposals WHERE slug = ? AND status = 'active'",
    args: [slug],
  });
  const row = result.rows[0] as unknown as ProposalRow | undefined;

  if (!row?.mdx) notFound();
  if (row.expires_at && new Date(row.expires_at).getTime() < Date.now()) {
    notFound();
  }

  return (
    <MotionRoot>
      <div className="proposal-root">
        <SmoothScroll />
        <MDXRemote
          source={row.mdx}
          components={proposalComponents}
          options={{ mdxOptions: {}, parseFrontmatter: false, scope: {}, blockJS: false }}
        />
      </div>
    </MotionRoot>
  );
}
