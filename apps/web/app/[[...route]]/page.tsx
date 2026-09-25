import Landing from "@/components/Landing";
import Login from "@/components/Login";
import Workspace from "@/components/Workspace";

export default async function Page({ params }: { params: Promise<{ route?: string[] }> }) {
  const { route = [] } = await params;
  if (route[0] === "login") return <Login />;
  if (!route.length) return <Landing />;
  return <Workspace />;
}
