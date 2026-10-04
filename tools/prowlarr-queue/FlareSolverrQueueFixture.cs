using System.Net.Http;
using System.Reflection;
using System.Threading;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using NzbDrone.Common.Http;
using NzbDrone.Core.IndexerProxies;
using NzbDrone.Core.IndexerProxies.FlareSolverr;
using NzbDrone.Core.Test.Framework;

namespace NzbDrone.Core.Test.IndexerTests
{
    [TestFixture]
    public class FlareSolverrQueueFixture : CoreTest<FlareSolverr>
    {
        [TestCase(false, "GET")]
        [TestCase(false, "POST")]
        [TestCase(true, "GET")]
        [TestCase(true, "POST")]
        public void should_separate_queue_wait_without_changing_execution_budget(bool waitForQueue, string method)
        {
            var settings = new FlareSolverrSettings { Host = "http://byparr:8191", RequestTimeout = 120 };
            typeof(FlareSolverrSettings).GetProperty("WaitForQueue")?.SetValue(settings, waitForQueue);
            Subject.Definition = new IndexerProxyDefinition { Settings = settings };
            var upstream = new HttpRequest("https://example.test/") { Method = new HttpMethod(method) };
            upstream.Headers.ContentType = "application/x-www-form-urlencoded";
            upstream.SetContent("value=one");
            var request = (HttpRequest)typeof(FlareSolverr)
                .GetMethod("GenerateFlareSolverrRequest", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(Subject, new object[] { upstream });

            Assert.That(JObject.Parse(request.GetContent())["maxTimeout"].Value<int>(), Is.EqualTo(120000));
            Assert.That(request.RequestTimeout, Is.EqualTo(waitForQueue ? Timeout.InfiniteTimeSpan : System.TimeSpan.FromSeconds(125)));
            Assert.That(request.Url.ToString(), Is.EqualTo("http://byparr:8191/v1"));
        }
    }
}
